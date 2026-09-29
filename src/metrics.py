"""Deterministic retrieval and answer metrics for FinGenEval.

Every function here is pure so each benchmark number can be recomputed and unit
tested without models or API keys.

# DESIGN: Answer-level metrics are lexical proxies. They check whether each
# answer sentence is supported by the retrieved context (terms and numbers),
# whether it carries a valid citation, and whether the system abstains when the
# corpus has no answer. They do not understand negation or paraphrase deeply.
# PRODUCTION: Pair these with an NLI or LLM-judge faithfulness check and a
# human-labeled calibration sample before relying on them for sign-off.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from .retrievers import RetrievalResult

CANNOT_DETERMINE_TEXT = "I cannot determine this from the provided documents."

# A claim sentence is supported when at least this share of its content terms
# (excluding terms copied from the question) appears in the retrieved context.
SUPPORT_THRESHOLD = 0.6
# Sentences with fewer content terms ("Yes.", "In summary:") are not claims.
MIN_CLAIM_TERMS = 3

STOP_WORDS = frozenset(ENGLISH_STOP_WORDS)
NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "fifteen": "15",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "ninety": "90",
}
TERM_PATTERN = re.compile(r"[a-z0-9%+<>]+(?:[-'][a-z0-9%+<>]+)*")
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
BRACKET_CITATION_PATTERN = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
FILENAME_PATTERN = re.compile(r"\b[\w-]+\.md\b")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------


def stem(term: str) -> str:
    """Apply a tiny suffix stemmer so inflections of a word share one stem.

    For example 'approve', 'approved', 'approves', and 'approving' all become
    'approv', while 'exceed', 'analysis', and 'process' keep their endings.
    """
    if len(term) <= 4 or not term.isalpha():
        return term
    if term.endswith("ies"):
        term = term[:-3] + "y"
    elif term.endswith("ing") and len(term) >= 7:
        term = term[:-3]
    elif term.endswith("ed") and not term.endswith("eed") and len(term) >= 6:
        term = term[:-2]
    elif term.endswith("es") and term[:-2].endswith(("s", "x", "z", "ch", "sh")):
        term = term[:-2]
    elif term.endswith("s") and not term.endswith(("ss", "is", "us")):
        term = term[:-1]
    return term[:-1] if term.endswith("e") and len(term) > 4 else term


def content_terms(text: str) -> set[str]:
    """Return stemmed, stopword-free terms with number words mapped to digits."""
    terms = set()
    for token in TERM_PATTERN.findall(str(text).lower()):
        for part in token.split("-"):
            part = NUMBER_WORDS.get(part, part)
            if part and part not in STOP_WORDS:
                terms.add(stem(part))
    return terms


def numbers_in(text: str) -> set[str]:
    """Extract numeric values, including spelled-out small numbers."""
    lowered = str(text).lower()
    found = set(NUMBER_PATTERN.findall(lowered))
    for word in re.findall(r"[a-z]+", lowered):
        if word in NUMBER_WORDS:
            found.add(NUMBER_WORDS[word])
    return found


def split_labels(value: object) -> list[str]:
    """Split a semicolon-delimited label cell, treating blanks and 'none' as empty."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    items = [item.strip() for item in str(value).split(";") if item.strip()]
    return [] if items == ["none"] else items


def section_key(result: RetrievalResult) -> str:
    """Identify a retrieved chunk by 'source#section', matching dataset labels."""
    return f"{result.source}#{result.section}"


# ---------------------------------------------------------------------------
# Retrieval metrics (labeled relevance, independent of the generator)
# ---------------------------------------------------------------------------


def relevance_flags(results: Sequence[RetrievalResult], relevant_sections: Sequence[str]) -> list[bool]:
    """Mark each retrieved chunk as relevant when its section is labeled relevant."""
    relevant = set(relevant_sections)
    return [section_key(item) in relevant for item in results]


def hit_at_k(flags: Sequence[bool]) -> float:
    """Return 1.0 when any relevant chunk was retrieved."""
    return float(any(flags))


def reciprocal_rank(flags: Sequence[bool]) -> float:
    """Return 1/rank of the first relevant chunk, or 0.0 when none is retrieved."""
    for rank, flag in enumerate(flags, start=1):
        if flag:
            return 1.0 / rank
    return 0.0


def contextual_precision(flags: Sequence[bool]) -> float:
    """Rank-weighted precision: mean precision@k over the ranks of relevant chunks.

    This rewards retrievers that place relevant evidence above irrelevant
    chunks, not only retrievers that include it somewhere in the top k.
    """
    hits = 0
    total = 0.0
    for rank, flag in enumerate(flags, start=1):
        if flag:
            hits += 1
            total += hits / rank
    return total / hits if hits else 0.0


def section_recall(results: Sequence[RetrievalResult], relevant_sections: Sequence[str]) -> float:
    """Share of labeled relevant sections present in the retrieved set."""
    if not relevant_sections:
        return math.nan
    retrieved = {section_key(item) for item in results}
    return sum(section in retrieved for section in relevant_sections) / len(relevant_sections)


def contextual_recall(results: Sequence[RetrievalResult], evidence: Sequence[str]) -> float:
    """Share of labeled evidence facts that appear verbatim in the retrieved context."""
    if not evidence:
        return math.nan
    context = " ".join(item.text for item in results).lower()
    return sum(fact.lower() in context for fact in evidence) / len(evidence)


# ---------------------------------------------------------------------------
# Answer metrics (require a generated answer)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimCheck:
    """Support and citation checks for one answer sentence."""

    sentence: str
    cited: bool
    invalid_citation: bool
    term_support: float
    unsupported_numbers: frozenset[str]

    @property
    def supported(self) -> bool:
        """A claim is supported when its terms and every number appear in context."""
        return self.term_support >= SUPPORT_THRESHOLD and not self.unsupported_numbers

    @property
    def flagged(self) -> bool:
        """A claim is a hallucination risk when unsupported or wrongly cited."""
        return not self.supported or self.invalid_citation


def is_abstention(answer: str) -> bool:
    """Detect the exact abstention sentence required by the strict prompt."""
    normalized = " ".join(str(answer).lower().split())
    return CANNOT_DETERMINE_TEXT.lower().rstrip(".") in normalized


def split_sentences(answer: str) -> list[str]:
    """Split an answer into sentences and bullet lines."""
    parts = SENTENCE_SPLIT_PATTERN.split(str(answer))
    return [part.strip(" -*\t") for part in parts if part and part.strip(" -*\t")]


def citation_status(sentence: str, results: Sequence[RetrievalResult]) -> tuple[bool, bool]:
    """Return (has_citation, has_invalid_citation) for one sentence.

    Valid citations are bracketed indices into the retrieved context ("[2]") or
    filenames of retrieved sources. Out-of-range indices and filenames that
    were not retrieved count as invalid (fabricated) citations.
    """
    retrieved_sources = {item.source for item in results}
    cited = False
    invalid = False
    for group in BRACKET_CITATION_PATTERN.findall(sentence):
        for raw in re.split(r"\s*[,;]\s*", group):
            cited = True
            if not 1 <= int(raw) <= len(results):
                invalid = True
    for filename in FILENAME_PATTERN.findall(sentence):
        cited = True
        if filename not in retrieved_sources:
            invalid = True
    return cited, invalid


def strip_citations(sentence: str) -> str:
    """Remove citation markers so they are not scored as claim content."""
    without_brackets = BRACKET_CITATION_PATTERN.sub(" ", sentence)
    return FILENAME_PATTERN.sub(" ", without_brackets)


def check_claims(answer: str, question: str, results: Sequence[RetrievalResult]) -> list[ClaimCheck]:
    """Check every claim sentence in an answer against the retrieved context."""
    context = " ".join(item.text for item in results)
    context_terms = content_terms(context)
    context_numbers = numbers_in(context)
    question_terms = content_terms(question)
    checks = []
    for sentence in split_sentences(answer):
        if is_abstention(sentence):
            continue
        body = strip_citations(sentence)
        terms = content_terms(body) - question_terms
        if len(content_terms(body)) < MIN_CLAIM_TERMS:
            continue
        support = len(terms & context_terms) / len(terms) if terms else 1.0
        cited, invalid = citation_status(sentence, results)
        checks.append(
            ClaimCheck(
                sentence=sentence,
                cited=cited,
                invalid_citation=invalid,
                term_support=support,
                unsupported_numbers=frozenset(numbers_in(body) - context_numbers),
            )
        )
    return checks


def answer_metrics(
    answer: str,
    question: str,
    results: Sequence[RetrievalResult],
    answerable: bool,
    reference_answer: str,
) -> dict[str, float]:
    """Compute grounding, citation, abstention, and correctness metrics.

    - faithfulness_proxy: share of claim sentences supported by retrieved context.
    - citation_coverage: share of claim sentences carrying a citation.
    - citation_validity: share of cited sentences whose citations point to retrieved evidence.
    - hallucination_risk: answerable questions -> share of claims that are unsupported
      or cite evidence that was not retrieved; unanswerable questions -> 1.0 unless
      the system abstains.
    - abstention_correct: abstained exactly when the question is unanswerable.
    - answer_correctness_proxy: share of reference-answer terms present in the answer.
    """
    abstained = is_abstention(answer)
    claims = check_claims(answer, question, results)
    cited = [claim for claim in claims if claim.cited]
    if answerable:
        risk = sum(claim.flagged for claim in claims) / len(claims) if claims else 0.0
        reference_terms = content_terms(reference_answer)
        correctness = (
            len(reference_terms & content_terms(answer)) / len(reference_terms)
            if reference_terms
            else math.nan
        )
    else:
        risk = 0.0 if abstained else 1.0
        correctness = math.nan
    return {
        "abstained": float(abstained),
        "abstention_correct": float(abstained != answerable),
        "claim_count": float(len(claims)),
        "faithfulness_proxy": (sum(c.supported for c in claims) / len(claims)) if claims else math.nan,
        "citation_coverage": (len(cited) / len(claims)) if claims else math.nan,
        "citation_validity": (sum(not c.invalid_citation for c in cited) / len(cited)) if cited else math.nan,
        "hallucination_risk": risk,
        "answer_correctness_proxy": correctness,
    }


ANSWER_METRIC_COLUMNS = [
    "abstained",
    "abstention_correct",
    "claim_count",
    "faithfulness_proxy",
    "citation_coverage",
    "citation_validity",
    "hallucination_risk",
    "answer_correctness_proxy",
]
