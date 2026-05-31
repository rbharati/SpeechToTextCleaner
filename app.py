from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import time
from grammer_model import correct_grammar
import os
from confiedence import score_text
from fluency import fluency_score
from openai_last_resort import correct_with_openai, should_use_llm
from semantic_correction import improve_semantic_word_choice
from semantic_guardrails import guard_semantic_rewrite
from spoken_grammar_repair import repair_spoken_grammar
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

USE_LLM_SEMANTIC_REWRITE = os.getenv("USE_LLM_SEMANTIC_REWRITE", "0") == "1"

if USE_LLM_SEMANTIC_REWRITE:
    from semantic_rewrite import semantic_rewrite

#from transformers import (
 #   AutoTokenizer,
  #  AutoModelForSeq2SeqLM
#)

app = Flask(__name__)

CORS(app)

print("Loading model...")

#model_name = "google/flan-t5-base"

#tokenizer = AutoTokenizer.from_pretrained(
 #   model_name
#)

#model = AutoModelForSeq2SeqLM.from_pretrained(
 #   model_name
#)


FILLER_WORDS = {
    "uh",
    "um",
    "hmm",
    "mmm",
}


def remove_extra_spaces(text):

    return re.sub(r'\s+', ' ', text).strip()


def remove_duplicate_words(text):

    words = text.split()

    cleaned = []

    prev_word = None

    for word in words:

        normalized = word.lower()

        if normalized != prev_word:

            cleaned.append(word)

        prev_word = normalized

    return " ".join(cleaned)


def remove_filler_words(text):

    words = text.split()

    cleaned = []

    for word in words:

        normalized = re.sub(r'[^\w]', '', word.lower())

        if normalized not in FILLER_WORDS:

            cleaned.append(word)

    return " ".join(cleaned)


def normalize_punctuation(text):

    text = re.sub(r'[.]{2,}', '.', text)

    text = re.sub(r'[,]{2,}', ',', text)

    text = re.sub(r'[!]{2,}', '!', text)

    text = re.sub(r'[?]{2,}', '?', text)

    return text


def add_terminal_punctuation(text):

    text = text.strip()

    if len(text) == 0:
        return text

    if text[-1] not in ['.', '?', '!']:

        text += '.'

    return text


def capitalize_sentences(text):

    sentence_endings = re.compile(r'([.!?]\s*)')

    parts = sentence_endings.split(text)

    corrected = []

    for part in parts:

        if len(part.strip()) == 0:
            corrected.append(part)
            continue

        if sentence_endings.match(part):

            corrected.append(part)

        else:
            stripped = part.strip()

            corrected.append(
                stripped[:1].upper() + stripped[1:]
            )

    return ''.join(corrected)


def normalize_text(text):

    text = remove_extra_spaces(text)

    text = remove_filler_words(text)

    text = remove_duplicate_words(text)

    text = normalize_punctuation(text)

    text = add_terminal_punctuation(text)

    text = capitalize_sentences(text)

    return text

print("Model loaded!")
@app.route("/")
def new_func():
    return ("hello")

def run_correction_pipeline(text, allow_llm=False, force_llm=False, confidence_threshold=75):
    latencies = {}

    # Layer 1: Normalization
    start = time.perf_counter()
    normalized = normalize_text(text)
    latencies["normalization_ms"] = round((time.perf_counter() - start) * 1000, 2)

    # Layer 2: Grammar Correction
    start = time.perf_counter()
    corrected = correct_grammar(normalized)
    latencies["grammar_corrected_ms"] = round((time.perf_counter() - start) * 1000, 2)

    # Layer 3: Spoken Grammar Repair
    start = time.perf_counter()
    spoken_grammar = repair_spoken_grammar(corrected)
    grammar_repaired = spoken_grammar["text"]
    latencies["spoken_grammar_ms"] = round((time.perf_counter() - start) * 1000, 2)

    # Layer 4: Semantic Word Choice
    start = time.perf_counter()
    semantic_word_choice = improve_semantic_word_choice(grammar_repaired)
    candidate_output = semantic_word_choice["text"]
    latencies["semantic_word_choice_ms"] = round((time.perf_counter() - start) * 1000, 2)

    # Scoring candidate output
    start = time.perf_counter()
    confidence = score_text(candidate_output)
    fluency = fluency_score(candidate_output)
    latencies["scoring_ms"] = round((time.perf_counter() - start) * 1000, 2)

    final_output = candidate_output
    semantic_rewrite_used = False
    semantic_rewrite_guard = None

    # Custom LLM decision using the dynamic confidence threshold
    reasons = []
    if confidence.get("score", 100) < confidence_threshold:
        reasons.append(f"confidence score below {confidence_threshold}")

    if fluency.get("confidence") == "LOW":
        reasons.append("fluency confidence is LOW")

    if (
        not spoken_grammar.get("changed")
        and not semantic_word_choice.get("changed")
        and confidence.get("score", 100) < 90
    ):
        reasons.append("cheap repair layers made no change")

    llm_decision = {
        "needed": len(reasons) > 0,
        "reasons": reasons,
    }

    llm_result = {
        "allowed": allow_llm,
        "forced": force_llm,
        "used": False,
        "needed": llm_decision["needed"],
        "reasons": llm_decision["reasons"],
    }

    latencies["semantic_rewrite_ms"] = 0.0
    if USE_LLM_SEMANTIC_REWRITE and (fluency["confidence"] == "MEDIUM" or fluency["confidence"] == "LOW"):
        start = time.perf_counter()
        print("corrected======", candidate_output)
        rewritten = semantic_rewrite(candidate_output)
        print("rewrittent======>", rewritten)
        rewritten_fluency = fluency_score(rewritten)
        semantic_rewrite_guard = guard_semantic_rewrite(
            candidate_output,
            rewritten
        )
        print("======>", rewritten_fluency)
        if (
            semantic_rewrite_guard["accepted"]
            and rewritten_fluency["perplexity"] < fluency["perplexity"]
        ):
            final_output = rewritten
            fluency = rewritten_fluency
            confidence = score_text(final_output)
            semantic_rewrite_used = True
        latencies["semantic_rewrite_ms"] = round((time.perf_counter() - start) * 1000, 2)

    latencies["llm_ms"] = 0.0
    if allow_llm and (force_llm or llm_decision["needed"]):
        start = time.perf_counter()
        openai_result = correct_with_openai(
            raw_text=text,
            deterministic_text=final_output,
        )
        latencies["llm_ms"] = round((time.perf_counter() - start) * 1000, 2)

        llm_result.update(openai_result)
        llm_result["used"] = openai_result.get("ok", False)

        if openai_result.get("ok"):
            llm_guard = guard_semantic_rewrite(
                final_output,
                openai_result["text"],
                minimum_similarity=0.55,
            )
            llm_result["guard"] = llm_guard

            if llm_guard["accepted"]:
                final_output = openai_result["text"]
                confidence = score_text(final_output)
                fluency = fluency_score(final_output)
            else:
                llm_result["used"] = False
                llm_result["rejected"] = True

    total_latency = sum(latencies.values())
    latencies["total_ms"] = round(total_latency, 2)

    return {
        "raw": text,
        "normalized": normalized,
        "grammar_corrected": corrected,
        "spoken_grammar": spoken_grammar,
        "corrected": final_output,
        "confidence": confidence,
        "fluency": fluency,
        "semantic_word_choice": semantic_word_choice,
        "semantic_rewrite_used": semantic_rewrite_used,
        "semantic_rewrite_guard": semantic_rewrite_guard,
        "llm": llm_result,
        "latencies": latencies
    }


@app.route('/correct', methods=['POST'])
def correct_text():
    data = request.json or {}
    text = data.get('text', '')
    confidence_threshold = int(data.get('confidence_threshold', 75))

    result = run_correction_pipeline(
        text,
        allow_llm=bool(data.get('allow_llm', False)),
        force_llm=bool(data.get('force_llm', False)),
        confidence_threshold=confidence_threshold
    )

    print(text)
    print(result["normalized"])
    print(result["grammar_corrected"])
    return jsonify(result)


@app.route('/correct/llm', methods=['POST'])
def correct_text_with_llm():
    data = request.json or {}
    text = data.get('text', '')
    confidence_threshold = int(data.get('confidence_threshold', 75))

    result = run_correction_pipeline(
        text,
        allow_llm=True,
        force_llm=True,
        confidence_threshold=confidence_threshold
    )

    return jsonify(result)


@app.route('/compare', methods=['POST'])
def compare_text():
    data = request.json or {}
    text = data.get('text', '')
    confidence_threshold = int(data.get('confidence_threshold', 75))

    # 1. Library Only Flow
    lib_start = time.perf_counter()
    lib_res = run_correction_pipeline(
        text,
        allow_llm=False,
        force_llm=False,
        confidence_threshold=confidence_threshold
    )
    lib_latency = round((time.perf_counter() - lib_start) * 1000, 2)

    # 2. Direct LLM Only Flow (Normalize first to give same starting ground)
    llm_start = time.perf_counter()
    norm_text = normalize_text(text)
    llm_res = correct_with_openai(
        raw_text=text,
        deterministic_text=norm_text
    )
    llm_latency = round((time.perf_counter() - llm_start) * 1000, 2)

    if llm_res.get("ok"):
        llm_output_text = llm_res["text"]
        llm_usage = llm_res["usage"]
    else:
        llm_output_text = norm_text
        llm_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}

    llm_confidence = score_text(llm_output_text)
    llm_fluency = fluency_score(llm_output_text)

    # 3. Hybrid Flow
    hybrid_start = time.perf_counter()
    hybrid_res = run_correction_pipeline(
        text,
        allow_llm=True,
        force_llm=False,
        confidence_threshold=confidence_threshold
    )
    hybrid_latency = round((time.perf_counter() - hybrid_start) * 1000, 2)

    comparison = {
        "raw": text,
        "library_only": {
            "text": lib_res["corrected"],
            "latency_ms": lib_latency,
            "confidence": lib_res["confidence"],
            "fluency": lib_res["fluency"],
            "llm_used": False,
            "tokens": 0,
            "cost_usd": 0.0,
            "pipeline_detail": lib_res
        },
        "llm_only": {
            "text": llm_output_text,
            "latency_ms": llm_latency,
            "confidence": llm_confidence,
            "fluency": llm_fluency,
            "llm_used": True,
            "tokens": llm_usage["total_tokens"],
            "cost_usd": llm_usage["cost_usd"]
        },
        "hybrid": {
            "text": hybrid_res["corrected"],
            "latency_ms": hybrid_latency,
            "confidence": hybrid_res["confidence"],
            "fluency": hybrid_res["fluency"],
            "llm_used": hybrid_res["llm"]["used"],
            "llm_needed": hybrid_res["llm"]["needed"],
            "llm_reasons": hybrid_res["llm"]["reasons"],
            "tokens": hybrid_res["llm"].get("usage", {}).get("total_tokens", 0) if hybrid_res["llm"]["used"] else 0,
            "cost_usd": hybrid_res["llm"].get("usage", {}).get("cost_usd", 0.0) if hybrid_res["llm"]["used"] else 0.0,
            "saved_by_libraries": not hybrid_res["llm"]["used"],
            "pipeline_detail": hybrid_res
        }
    }
    return jsonify(comparison)




    

   
if __name__ == '__main__':
    #app.run(debug=True)
    app.run(
    host="0.0.0.0",
    port=5000,
    debug=True,
    use_reloader=False
)
