"""Integrity checks that keep evaluation labels consistent with the indexed corpus."""

from src.evaluator import load_questions
from src.metrics import split_labels
from src.retrievers import build_chunks

CHUNKS = {f"{chunk.source}#{chunk.section}": chunk.text.lower() for chunk in build_chunks()}
QUESTIONS = load_questions()


def test_relevant_sections_exist_in_index():
    for _, row in QUESTIONS[QUESTIONS["answerable"]].iterrows():
        sections = split_labels(row["relevant_sections"])
        assert sections, row["question"]
        missing = [section for section in sections if section not in CHUNKS]
        assert not missing, (row["question"], missing)


def test_expected_sources_match_relevant_sections():
    for _, row in QUESTIONS[QUESTIONS["answerable"]].iterrows():
        from_sections = {section.split("#")[0] for section in split_labels(row["relevant_sections"])}
        assert from_sections == set(split_labels(row["expected_sources"])), row["question"]


def test_every_evidence_fact_appears_in_a_relevant_section():
    for _, row in QUESTIONS[QUESTIONS["answerable"]].iterrows():
        texts = [CHUNKS[section] for section in split_labels(row["relevant_sections"])]
        for fact in split_labels(row["evidence_keywords"]):
            assert any(fact.lower() in text for text in texts), (row["question"], fact)


def test_unanswerable_questions_have_no_labels():
    unanswerable = QUESTIONS[~QUESTIONS["answerable"]]
    assert len(unanswerable) >= 5
    for _, row in unanswerable.iterrows():
        assert not split_labels(row["relevant_sections"])
        assert not split_labels(row["evidence_keywords"])


def test_questions_do_not_copy_long_evidence_phrases():
    """Guard against questions that quote the labeled evidence verbatim."""
    for _, row in QUESTIONS[QUESTIONS["answerable"]].iterrows():
        question = row["question"].lower()
        for fact in split_labels(row["evidence_keywords"]):
            if len(fact.split()) >= 3:
                assert fact.lower() not in question, (row["question"], fact)
