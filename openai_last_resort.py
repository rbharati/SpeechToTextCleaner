import json
import os
import urllib.error
import urllib.request


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def _load_api_key():
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        return api_key

    env_path = os.path.join(os.path.dirname(__file__), ".env")

    if not os.path.exists(env_path):
        return None

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()

            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)

            if key.strip() == "OPENAI_API_KEY":
                return value.strip().strip('"').strip("'")

    return None


def _extract_output_text(response_json):
    if "choices" in response_json and len(response_json["choices"]) > 0:
        choice = response_json["choices"][0]
        if "message" in choice and "content" in choice["message"]:
            return choice["message"]["content"].strip()

    if response_json.get("output_text"):
        return response_json["output_text"].strip()

    chunks = []

    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])

    return "".join(chunks).strip()


def correct_with_openai(raw_text, deterministic_text, model=None):
    api_key = _load_api_key()

    if not api_key:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY is not set",
        }

    selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

    prompt = (
        "Correct the transcript into polished natural English.\n"
        "Keep the original meaning, names, numbers, tense, and negation.\n"
        "Add missing helper words, articles, punctuation, and sentence breaks.\n"
        "Do not add new facts. Return only the corrected text.\n\n"
        f"Original transcript:\n{raw_text}\n\n"
        f"Best deterministic correction so far:\n{deterministic_text}"
    )

    payload = {
        "model": selected_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a grammar correction engine for spoken English and blog drafts. "
                    "Return only the corrected text."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_tokens": 220,
    }

    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_json = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "model": selected_model,
            "error": f"OpenAI API error {error.code}",
            "details": body[:500],
        }
    except Exception as error:
        return {
            "ok": False,
            "model": selected_model,
            "error": str(error),
        }

    output_text = _extract_output_text(response_json)

    if not output_text:
        return {
            "ok": False,
            "model": selected_model,
            "error": "OpenAI response did not contain corrected text",
        }

    usage = response_json.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0) or (input_tokens + output_tokens)

    # Estimate cost for gpt-4o-mini ($0.150 per 1M input, $0.600 per 1M output)
    cost = (input_tokens * 0.150 / 1_000_000) + (output_tokens * 0.600 / 1_000_000)

    return {
        "ok": True,
        "model": selected_model,
        "text": output_text,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost, 6),
        },
    }


def should_use_llm(confidence, fluency, spoken_grammar, semantic_word_choice):
    reasons = []

    if confidence.get("score", 100) < 75:
        reasons.append("confidence score below 75")

    if fluency.get("confidence") == "LOW":
        reasons.append("fluency confidence is LOW")

    if (
        not spoken_grammar.get("changed")
        and not semantic_word_choice.get("changed")
        and confidence.get("score", 100) < 90
    ):
        reasons.append("cheap repair layers made no change")

    return {
        "needed": len(reasons) > 0,
        "reasons": reasons,
    }
