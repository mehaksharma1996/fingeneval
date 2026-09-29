from types import SimpleNamespace

from src.enterprise.evaluation import compare_case
from src.enterprise.schemas import SystemResponse


def response(answer: str, citations: list[str]) -> SystemResponse:
    return SystemResponse(
        answer=answer,
        citations=citations,
        latency_ms=1,
        input_tokens=10,
        output_tokens=10,
        estimated_cost_usd=0,
        provider_request_id="test",
    )


def test_unsupported_deadline_is_a_regression():
    evidence = "aml.md#SAR Filing Timelines"
    case = SimpleNamespace(
        case_key="aml-sar-deadline",
        required_evidence=[evidence],
        abstention_expected=False,
        reference_answer="File within 30 days; 60 days if no suspect.",
        expected_behavior="Use policy deadline",
        category="incorrect_policy_deadline",
        tags=["deadline"],
        release_blocking=True,
        risk_weight=10,
    )
    baseline = response(case.reference_answer, [evidence])
    candidate = response("File within 45 days; 60 days if no suspect.", [evidence])
    result = compare_case(case, baseline, candidate)
    assert result.baseline_passed is True
    assert result.candidate_passed is False
    assert result.regression is True
    assert result.mandatory_failed is True
    assert result.unsupported_numeric_claims == 1
    unsupported = [a for a in result.evidence_verification.assertions if not a.supported]
    assert [item.claim for item in unsupported] == ["45"]


def test_invalid_citation_fails_supported_answer():
    case = SimpleNamespace(
        case_key="case",
        required_evidence=["approved.md#Policy"],
        abstention_expected=False,
        reference_answer="The threshold is 30%.",
        expected_behavior="Use approved evidence",
        category="threshold",
        tags=[],
        release_blocking=False,
        risk_weight=2,
    )
    baseline = response(case.reference_answer, ["approved.md#Policy"])
    candidate = response(case.reference_answer, ["other.md#Policy"])
    result = compare_case(case, baseline, candidate)
    assert result.candidate_passed is False
    assert result.citation_validity == 0
