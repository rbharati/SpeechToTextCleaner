import re

from fluency import fluency_score
from semantic_guardrails import guard_semantic_rewrite


CONFUSION_GROUPS = [
    {"there", "their", "they're"},
    {"to", "too", "two"},
    {"your", "you're"},
    {"its", "it's"},
    {"then", "than"},
    {"affect", "effect"},
    {"accept", "except"},
    {"advice", "advise"},
    {"weather", "whether"},
    {"principal", "principle"},
    {"loose", "lose"},
    {"passed", "past"},
    {"peace", "piece"},
    {"right", "write"},
    {"meet", "meat"},
    {"hear", "here"},
    {"no", "know"},
    {"by", "buy", "bye"},
]

CONFUSION_MAP = {
    word: sorted(group - {word})
    for group in CONFUSION_GROUPS
    for word in group
}


def _match_case(original, replacement):
    if original.isupper():
        return replacement.upper()

    if original[:1].isupper():
        return replacement.capitalize()

    return replacement


def _replace_word(words, index, replacement):
    updated = words[:]
    original = updated[index]
    prefix = re.match(r"^\W*", original).group(0)
    suffix = re.search(r"\W*$", original).group(0)
    bare = original[len(prefix): len(original) - len(suffix) if suffix else len(original)]
    updated[index] = f"{prefix}{_match_case(bare, replacement)}{suffix}"
    return " ".join(updated)


def _semantic_candidates(text):
    words = text.split()
    candidates = []

    for index, word in enumerate(words):
        bare_word = re.sub(r"^\W+|\W+$", "", word).lower()

        for replacement in CONFUSION_MAP.get(bare_word, []):
            candidates.append(_replace_word(words, index, replacement))

    return candidates


def improve_semantic_word_choice(text):
    original_fluency = fluency_score(text)
    best_text = text
    best_fluency = original_fluency
    best_guard = {
        "accepted": True,
        "similarity": 1.0,
        "reasons": [],
    }

    checked = []

    for candidate in _semantic_candidates(text):
        guard = guard_semantic_rewrite(text, candidate, minimum_similarity=0.78)

        if not guard["accepted"]:
            checked.append({
                "text": candidate,
                "accepted": False,
                "guard": guard,
            })
            continue

        candidate_fluency = fluency_score(candidate)
        checked.append({
            "text": candidate,
            "accepted": True,
            "fluency": candidate_fluency,
            "guard": guard,
        })

        if candidate_fluency["perplexity"] < best_fluency["perplexity"]:
            best_text = candidate
            best_fluency = candidate_fluency
            best_guard = guard

    return {
        "text": best_text,
        "changed": best_text != text,
        "original_fluency": original_fluency,
        "fluency": best_fluency,
        "guard": best_guard,
        "checked": checked[:5],
    }
