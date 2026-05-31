import math
import torch

from transformers import (
    GPT2LMHeadModel,
    GPT2TokenizerFast
)

MODEL_NAME = "distilgpt2"

print("Loading fluency model...")

tokenizer = GPT2TokenizerFast.from_pretrained(
    MODEL_NAME
)

model = GPT2LMHeadModel.from_pretrained(
    MODEL_NAME
)

model.eval()

print("Fluency model loaded!")


def calculate_perplexity(text):

    encodings = tokenizer(
        text,
        return_tensors="pt"
    )

    input_ids = encodings.input_ids

    with torch.no_grad():

        outputs = model(
            input_ids,
            labels=input_ids
        )

        loss = outputs.loss

    perplexity = math.exp(loss.item())

    return perplexity


def fluency_score(text):

    perplexity = calculate_perplexity(text)

    # Lower perplexity = better
    # Calibrated for distilgpt2:
    # < 45: HIGH (Standard clean sentence)
    # < 95: MEDIUM (Correct but slightly conversational/simple)
    # >= 95: LOW (Fragmented, scrambled, or poor phrasing)
    if perplexity < 45:

        confidence = "HIGH"

    elif perplexity < 95:

        confidence = "MEDIUM"

    else:

        confidence = "LOW"

    return {
        "perplexity": round(perplexity, 2),
        "confidence": confidence
    }