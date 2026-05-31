import re
from difflib import SequenceMatcher

import spacy


nlp = spacy.load("en_core_web_sm")

NEGATIONS = {
    "no",
    "not",
    "never",
    "none",
    "nothing",
    "nowhere",
    "neither",
    "nor",
    "cannot",
    "can't",
    "dont",
    "don't",
    "didnt",
    "didn't",
    "wont",
    "won't",
    "isnt",
    "isn't",
    "wasnt",
    "wasn't",
    "shouldnt",
    "shouldn't",
    "couldnt",
    "couldn't",
}

CONTENT_POS = {
    "NOUN",
    "PROPN",
    "VERB",
    "ADJ",
    "ADV",
    "NUM",
}


def _number_tokens(text):
    return set(re.findall(r"\b\d+(?:[.,]\d+)?\b", text))


def _negations(doc):
    return {
        token.text.lower()
        for token in doc
        if token.text.lower() in NEGATIONS or token.dep_ == "neg"
    }


def _entities(doc):
    return {
        (ent.text.lower(), ent.label_)
        for ent in doc.ents
        if ent.label_ in {"PERSON", "ORG", "GPE", "DATE", "TIME", "MONEY", "PERCENT", "CARDINAL"}
    }


def _content_lemmas(doc):
    return {
        token.lemma_.lower()
        for token in doc
        if token.pos_ in CONTENT_POS
        and not token.is_stop
        and not token.is_punct
        and token.lemma_.strip()
    }


def semantic_similarity(source, candidate):
    source_doc = nlp(source)
    candidate_doc = nlp(candidate)

    source_lemmas = _content_lemmas(source_doc)
    candidate_lemmas = _content_lemmas(candidate_doc)

    if source_lemmas or candidate_lemmas:
        overlap = len(source_lemmas & candidate_lemmas)
        union = len(source_lemmas | candidate_lemmas)
        lemma_score = overlap / union if union else 1.0
    else:
        lemma_score = 1.0

    sequence_score = SequenceMatcher(None, source.lower(), candidate.lower()).ratio()

    return round((lemma_score * 0.65) + (sequence_score * 0.35), 3)


def guard_semantic_rewrite(source, candidate, minimum_similarity=0.72):
    source_doc = nlp(source)
    candidate_doc = nlp(candidate)

    reasons = []
    similarity = semantic_similarity(source, candidate)

    source_negations = _negations(source_doc)
    candidate_negations = _negations(candidate_doc)
    if source_negations != candidate_negations:
        reasons.append("negation changed")

    source_numbers = _number_tokens(source)
    candidate_numbers = _number_tokens(candidate)
    if source_numbers != candidate_numbers:
        reasons.append("numbers changed")

    source_entities = _entities(source_doc)
    candidate_entities = _entities(candidate_doc)
    if not source_entities.issubset(candidate_entities):
        reasons.append("named entities changed")

    if similarity < minimum_similarity:
        reasons.append(f"semantic similarity too low: {similarity}")

    return {
        "accepted": len(reasons) == 0,
        "similarity": similarity,
        "reasons": reasons,
    }
