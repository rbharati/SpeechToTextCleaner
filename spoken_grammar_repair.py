import re


SUBJECT_BE = {
    "i": "am",
    "you": "are",
    "we": "are",
    "they": "are",
    "he": "is",
    "she": "is",
    "it": "is",
    "this": "is",
    "that": "is",
}

COMMON_ADJECTIVES = {
    "able",
    "available",
    "bad",
    "beautiful",
    "best",
    "better",
    "big",
    "blue",
    "busy",
    "clear",
    "correct",
    "different",
    "easy",
    "fine",
    "free",
    "good",
    "great",
    "happy",
    "important",
    "interesting",
    "late",
    "new",
    "possible",
    "ready",
    "right",
    "same",
    "simple",
    "sorry",
    "sure",
    "true",
    "wrong",
}

PASSIVE_FEELING_VERBS = {
    "amazed",
    "confused",
    "excited",
    "fascinated",
    "impressed",
    "interested",
    "mesmerized",
    "shocked",
    "surprised",
    "tired",
}


def _preserve_subject_case(subject):
    return "I" if subject.lower() == "i" else subject


def _replace_subject_be(match):
    subject = _preserve_subject_case(match.group(1))
    word = match.group(2)
    be = SUBJECT_BE[subject.lower()]
    return f"{subject} {be} {word}"


def _insert_name_be(match):
    name = match.group(1)
    return f"my name is {name}"


def _split_long_spoken_turn(text):
    text = re.sub(
        r"\b(hello|hi|hey)\s+my name\b",
        lambda match: f"{match.group(1)}, my name",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b(my name is [A-Z][A-Za-z.'-]+)\s+(I|We|This|Today)\b",
        r"\1. \2",
        text,
    )

    text = re.sub(
        r"\b(class \d+)\s+(I|We|This|Today|Now|In this)\b",
        r"\1. \2",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b(class \d+|school|college|university|work)\s+(my\s+(favourite|favorite)\b)",
        r"\1 and \2",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b([a-z]+)\s+(it|this|that)\s+(is|was|are|were)\b",
        r"\1. \2 \3",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b([a-z]+)\s+(I|We|He|She|They|You)\s+(am|was|are|were|is)\b",
        r"\1. \2 \3",
        text,
    )

    return text


def _repair_missing_be(text):
    adjective_pattern = "|".join(sorted(COMMON_ADJECTIVES))
    feeling_pattern = "|".join(sorted(PASSIVE_FEELING_VERBS))

    text = re.sub(
        rf"\b(I|you|we|they|he|she|it|this|that)\s+({adjective_pattern})\b",
        _replace_subject_be,
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        rf"\b(I|you|we|they|he|she|it|this|that)\s+(so|very|really|too)\s+({adjective_pattern})\b",
        lambda match: (
            f"{_preserve_subject_case(match.group(1))} "
            f"{SUBJECT_BE[match.group(1).lower()]} {match.group(2)} {match.group(3)}"
        ),
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        rf"\b(I|you|we|they|he|she|it|this|that)\s+({feeling_pattern})\b",
        _replace_subject_be,
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bthere\s+(is|was|are|were)\s+so\s+([a-z]+)\s+([a-z]+)\b",
        r"there \1 a very \2 \3",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bthere\s+so\s+([a-z]+)\s+([a-z]+)\b",
        r"there was a very \1 \2",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bthere\s+(big|small|beautiful|blue|huge|large|great|nice)\s+([a-z]+)\b",
        r"there was a \1 \2",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b(I|you|we|they)\s+going\s+to\b",
        lambda match: f"{_preserve_subject_case(match.group(1))} {SUBJECT_BE[match.group(1).lower()]} going to",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b(he|she|it)\s+going\s+to\b",
        lambda match: f"{match.group(1)} is going to",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b(this|that)\s+(blog|post|video|sentence|paragraph)\s+about\b",
        lambda match: f"{match.group(1)} {match.group(2)} is about",
        text,
        flags=re.IGNORECASE,
    )

    return text


def _repair_verb_patterns(text):
    replacements = [
        (r"\bI am study\b", "I study"),
        (r"\bI am go\b", "I go"),
        (r"\bI am want\b", "I want"),
        (r"\bI want share\b", "I want to share"),
        (r"\bI want explain\b", "I want to explain"),
        (r"\bI want tell\b", "I want to tell"),
        (r"\bI need explain\b", "I need to explain"),
        (r"\bgoing explain\b", "going to explain"),
        (r"\bgoing share\b", "going to share"),
        (r"\bgoing tell\b", "going to tell"),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(
        r"\b(I|we|they|you)\s+study\s+class\s+(\d+)\b",
        lambda match: f"{_preserve_subject_case(match.group(1))} study in class {match.group(2)}",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b(he|she)\s+study\s+class\s+(\d+)\b",
        lambda match: f"{match.group(1)} studies in class {match.group(2)}",
        text,
        flags=re.IGNORECASE,
    )

    return text


def _repair_intro_patterns(text):
    # Case 1: Already has "is" or "Is". Ensure "is" is lowercase and name is capitalized!
    text = re.sub(
        r"\bmy name\s+(is|Is)\s+([a-zA-Z])([a-zA-Z.'-]*)\b",
        lambda m: f"my name is {m.group(2).upper()}{m.group(3)}",
        text
    )

    # Case 2: Missing "is" completely. E.g., "my name Raj" -> "my name is Raj"
    # The name must not be "is", "Is", "was", "are", "were".
    text = re.sub(
        r"\bmy\s+name\s+(?!is\b|Is\b|was\b|are\b|were\b)([a-zA-Z])([a-zA-Z.'-]*)\b",
        lambda m: f"my name is {m.group(1).upper()}{m.group(2)}",
        text,
        flags=re.IGNORECASE
    )

    return text


def _capitalize_i(text):
    return re.sub(r"\bi\b", "I", text)


def _repair_past_context(text):
    has_past_context = re.search(
        r"\b(yesterday|last night|last week|last month|was|were|traveled|travelled|went|saw)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not has_past_context:
        return text

    feeling_pattern = "|".join(sorted(PASSIVE_FEELING_VERBS))

    text = re.sub(
        rf"\b(I|he|she|it|this|that)\s+is\s+({feeling_pattern})\b",
        lambda match: f"{_preserve_subject_case(match.group(1))} was {match.group(2)}",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        rf"\b(I|he|she|it|this|that)\s+am\s+({feeling_pattern})\b",
        lambda match: f"{_preserve_subject_case(match.group(1))} was {match.group(2)}",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b(it|this|that)\s+is\s+(so|very|really|too)\b",
        lambda match: f"{match.group(1)} was {match.group(2)}",
        text,
        flags=re.IGNORECASE,
    )

    return text


def _capitalize_sentence_starts(text):
    def capitalize_after_boundary(match):
        return f"{match.group(1)}{match.group(2).upper()}"

    text = text[:1].upper() + text[1:] if text else text
    return re.sub(r"([.!?]\s+)([a-z])", capitalize_after_boundary, text)


def _tidy_spacing(text):
    text = re.sub(r"\s+([.,!?])", r"\1", text)
    text = re.sub(r"([.,!?])([^\s])", r"\1 \2", text)
    return re.sub(r"\s+", " ", text).strip()


COMMON_PLACES_WITH_THE = {
    "park", "store", "office", "gym", "market", "bank", "mall", "beach",
    "movies", "theater", "station", "airport", "zoo", "library", "hospital",
    "restaurant", "hotel", "playground", "garden", "city",
}

COMMON_PLACES_WITHOUT_THE = {
    "school", "work", "college", "university", "church", "bed", "class",
}


def _repair_missing_prepositions(text):
    movement_verbs = r"(come\s+with\s+me|go|come|walk|run|drive|ride|travel|headed|heading)"
    
    # 1. Places with "the"
    places_with_the_pattern = "|".join(sorted(COMMON_PLACES_WITH_THE))
    text = re.sub(
        rf"\b{movement_verbs}\s+({places_with_the_pattern})\b",
        lambda match: f"{match.group(1)} to the {match.group(2)}",
        text,
        flags=re.IGNORECASE
    )
    
    # 2. Places without "the"
    places_without_the_pattern = "|".join(sorted(COMMON_PLACES_WITHOUT_THE))
    text = re.sub(
        rf"\b{movement_verbs}\s+({places_without_the_pattern})\b",
        lambda match: f"{match.group(1)} to {match.group(2)}",
        text,
        flags=re.IGNORECASE
    )
    
    # 3. Fix cases with "to" but missing "the"
    text = re.sub(
        rf"\b{movement_verbs}\s+to\s+({places_with_the_pattern})\b",
        lambda match: f"{match.group(1)} to the {match.group(2)}",
        text,
        flags=re.IGNORECASE
    )
    
    return text


def _repair_possessive_be(text):
    possessive_subjects = r"(sport|hobby|color|colour|food|subject|movie|game|dream)"
    text = re.sub(
        rf"\bmy\s+(favourite|favorite)\s+{possessive_subjects}\s+(?!is\b|was\b|are\b|were\b)([a-z]+)\b",
        lambda match: f"my {match.group(1)} {match.group(2)} is {match.group(3)}",
        text,
        flags=re.IGNORECASE
    )
    return text


def repair_spoken_grammar(text):
    original = text
    repaired = text

    repaired = _capitalize_i(repaired)
    repaired = _repair_intro_patterns(repaired)
    repaired = _repair_missing_be(repaired)
    repaired = _repair_possessive_be(repaired)
    repaired = _repair_verb_patterns(repaired)
    repaired = _repair_missing_prepositions(repaired)
    repaired = _split_long_spoken_turn(repaired)
    repaired = _repair_past_context(repaired)
    repaired = _tidy_spacing(repaired)
    repaired = _capitalize_sentence_starts(repaired)

    return {
        "text": repaired,
        "changed": repaired != original,
    }
