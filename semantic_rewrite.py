from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM
)

MODEL_NAME = "google/flan-t5-large"

print("Loading semantic rewrite model...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)

model = AutoModelForSeq2SeqLM.from_pretrained(
    MODEL_NAME
)

print("Semantic rewrite model loaded!")


def semantic_rewrite(text):

    prompt = f"""
Rewrite the following spoken transcript into a natural,
grammatically correct English sentence.

Transcript:
{text}

Rewritten:
"""

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        max_length=128,
        truncation=True
    )

    outputs = model.generate(
    **inputs,
    max_new_tokens=64,
    num_beams=4,
    repetition_penalty=1.2,
    length_penalty=1.0,
    early_stopping=True
    )
    rewritten = tokenizer.decode(
        outputs[0],
        skip_special_tokens=True
    )

    print("final rewrite===>",rewritten)
    return rewritten