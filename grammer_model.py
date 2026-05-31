from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM
)

MODEL_NAME = "prithivida/grammar_error_correcter_v1"

print("Loading grammar model...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)

model = AutoModelForSeq2SeqLM.from_pretrained(
    MODEL_NAME
)

print("Grammar model loaded!")


def correct_grammar(text):

    input_text = f"gec: {text}"

    inputs = tokenizer.encode(
        input_text,
        return_tensors="pt",
        max_length=128,
        truncation=True
    )

    outputs = model.generate(
        inputs,
        max_length=128,
        num_beams=4,
        early_stopping=True
    )

    corrected = tokenizer.decode(
        outputs[0],
        skip_special_tokens=True
    )

    return corrected