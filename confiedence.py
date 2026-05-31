import re
import spacy

nlp = spacy.load("en_core_web_sm")


def score_text(text):

    score = 100

    reasons = []

    doc = nlp(text)

    words = [token.text.lower() for token in doc]

    # -----------------------------
    # 1. Repeated words
    # -----------------------------

    repeated_count = 0

    for i in range(1, len(words)):

        if words[i] == words[i - 1]:

            repeated_count += 1

    if repeated_count > 0:

        penalty = repeated_count * 10

        score -= penalty

        reasons.append(
            f"Repeated words: -{penalty}"
        )

    # -----------------------------
    # 2. Verb detection
    # -----------------------------

    verbs = [
        token for token in doc
        if token.pos_ == "VERB"
    ]

    if len(verbs) == 0:

        score -= 30

        reasons.append(
            "No clear verb detected: -30"
        )

    # -----------------------------
    # 3. Sentence length
    # -----------------------------

    if len(words) < 3:

        score -= 20

        reasons.append(
            "Sentence too short: -20"
        )

    # -----------------------------
    # 4. Excessive fillers
    # -----------------------------

    fillers = {
        "uh",
        "um",
        "like",
        "basically"
    }

    filler_count = sum(
        1 for word in words
        if word in fillers
    )

    if filler_count > 2:

        penalty = filler_count * 5

        score -= penalty

        reasons.append(
            f"Too many fillers: -{penalty}"
        )

    # -----------------------------
    # 5. Missing punctuation
    # -----------------------------

    if text[-1] not in ['.', '?', '!']:

        score -= 10

        reasons.append(
            "Missing punctuation: -10"
        )

    # -----------------------------
    # Normalize
    # -----------------------------

    score = max(score, 0)

    return {
        "score": score,
        "reasons": reasons
    }