"""Unit tests for deterministic retrieval and answer metrics."""

import math

import pytest

from src import metrics
from src.retrievers import RetrievalResult


def result(source: str, section: str, text: str) -> RetrievalResult:
    return RetrievalResult(text, source, section, section, 1.0, "test")


SAR = result(
    "aml.md",
    "SAR Filing Timelines",
    "AML: SAR Filing Timelines - AML SAR filing must occur within 30 days of suspicion, 60 days maximum. "
    "Missed SAR timelines must be escalated to AML compliance leadership.",
)
BASEL = result("basel.md", "Stress Testing", "Basel: Stress Testing - stress results inform capital buffers.")
QUESTION = "How long does the bank have to file a SAR?"


def test_rank_metrics_reward_relevant_evidence_ranked_first():
    first = metrics.relevance_flags([SAR, BASEL], ["aml.md#SAR Filing Timelines"])
    second = metrics.relevance_flags([BASEL, SAR], ["aml.md#SAR Filing Timelines"])
    assert metrics.reciprocal_rank(first) == 1.0
    assert metrics.reciprocal_rank(second) == 0.5
    assert metrics.contextual_precision(first) == 1.0
    assert metrics.contextual_precision(second) == 0.5
    assert metrics.hit_at_k(metrics.relevance_flags([BASEL], ["aml.md#SAR Filing Timelines"])) == 0.0


def test_contextual_precision_averages_precision_at_each_relevant_rank():
    assert metrics.contextual_precision([True, False, True]) == pytest.approx((1 + 2 / 3) / 2)


def test_contextual_recall_counts_evidence_facts():
    assert metrics.contextual_recall([SAR], ["within 30 days of suspicion", "60 days maximum"]) == 1.0
    assert metrics.contextual_recall([BASEL], ["within 30 days of suspicion", "capital buffers"]) == 0.5
    assert math.isnan(metrics.contextual_recall([SAR], []))


def test_grounded_cited_answer_scores_well():
    answer = "A SAR must be filed within 30 days of suspicion, with a 60 days maximum [1]."
    scores = metrics.answer_metrics(
        answer, QUESTION, [SAR], True, "within 30 days of suspicion; 60 days maximum"
    )
    assert scores["faithfulness_proxy"] == 1.0
    assert scores["citation_coverage"] == 1.0
    assert scores["citation_validity"] == 1.0
    assert scores["hallucination_risk"] == 0.0
    assert scores["abstention_correct"] == 1.0


def test_unsupported_number_is_flagged_as_hallucination():
    answer = "A SAR must be filed within 45 days of suspicion [1]."
    scores = metrics.answer_metrics(answer, QUESTION, [SAR], True, "within 30 days")
    assert scores["faithfulness_proxy"] == 0.0
    assert scores["hallucination_risk"] == 1.0


def test_unsupported_content_is_flagged():
    answer = "Regulators impose criminal penalties and freeze accounts immediately [1]."
    scores = metrics.answer_metrics(answer, QUESTION, [SAR], True, "within 30 days")
    assert scores["faithfulness_proxy"] == 0.0


def test_fabricated_citation_is_invalid_and_risky():
    answer = "A SAR must be filed within 30 days of suspicion [4]."
    scores = metrics.answer_metrics(answer, QUESTION, [SAR], True, "within 30 days")
    assert scores["faithfulness_proxy"] == 1.0
    assert scores["citation_validity"] == 0.0
    assert scores["hallucination_risk"] == 1.0


def test_citation_coverage_is_per_sentence():
    answer = (
        "A SAR must be filed within 30 days of suspicion [1]. "
        "Missed SAR timelines must be escalated to AML compliance leadership."
    )
    scores = metrics.answer_metrics(answer, QUESTION, [SAR], True, "within 30 days")
    assert scores["claim_count"] == 2
    assert scores["citation_coverage"] == 0.5


def test_filename_citations_are_validated_against_retrieved_sources():
    assert metrics.citation_status("Filed within 30 days (aml.md).", [SAR]) == (True, False)
    assert metrics.citation_status("Filed within 30 days (other.md).", [SAR]) == (True, True)


def test_abstention_scoring():
    refusal = metrics.CANNOT_DETERMINE_TEXT
    unanswerable_refused = metrics.answer_metrics(refusal, "Crypto reserve ratio?", [BASEL], False, "")
    assert unanswerable_refused["abstention_correct"] == 1.0
    assert unanswerable_refused["hallucination_risk"] == 0.0

    unanswerable_answered = metrics.answer_metrics(
        "The crypto reserve ratio is 12 percent [1].", "Crypto reserve ratio?", [BASEL], False, ""
    )
    assert unanswerable_answered["abstention_correct"] == 0.0
    assert unanswerable_answered["hallucination_risk"] == 1.0

    false_refusal = metrics.answer_metrics(refusal, QUESTION, [SAR], True, "within 30 days")
    assert false_refusal["abstained"] == 1.0
    assert false_refusal["abstention_correct"] == 0.0
    assert math.isnan(false_refusal["faithfulness_proxy"])


def test_stemmer_is_consistent_across_inflections():
    for group in [
        ("approve", "approved", "approves", "approving"),
        ("exceed", "exceeds", "exceeded"),
        ("theme", "themes"),
        ("review", "reviews", "reviewed"),
        ("process", "processes"),
    ]:
        assert len({metrics.stem(word) for word in group}) == 1, group
    assert metrics.stem("analysis") == "analysis"


def test_answer_grounded_only_in_unretrieved_evidence_is_unfaithful():
    answer = "Recurring complaint themes require root-cause analysis and corrective action plans [1]."
    scores = metrics.answer_metrics(answer, "repeat grievances?", [BASEL], True, "root-cause analysis")
    assert scores["faithfulness_proxy"] == 0.0


def test_spelled_numbers_match_digits():
    complaint = result("c.md", "Response Timelines", "a substantive response within thirty calendar days")
    answer = "A substantive response is due within 30 calendar days [1]."
    scores = metrics.answer_metrics(answer, "complaint timing?", [complaint], True, "thirty days")
    assert scores["faithfulness_proxy"] == 1.0
