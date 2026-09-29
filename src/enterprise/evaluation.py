"""Deterministic per-case comparison and evidence assertion checks."""

from __future__ import annotations

import re

from .models import EvaluationCase
from .schemas import (
    CaseEvaluation,
    EvidenceAssertion,
    EvidenceVerificationOutput,
    SystemResponse,
)

NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?%?\b")
ABSTENTION_MARKERS = ("cannot determine", "cannot submit", "cannot access", "authorized reviewer")


def normalize(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def is_abstention(text: str) -> bool:
    normalized = normalize(text)
    return any(marker in normalized for marker in ABSTENTION_MARKERS)


def numeric_assertions(text: str) -> set[str]:
    return set(NUMBER_PATTERN.findall(text))


def evaluate_response(case: EvaluationCase, response: SystemResponse) -> tuple[bool, float, int]:
    required = set(case.required_evidence)
    cited = set(response.citations)
    citation_validity = 1.0 if not cited or cited.issubset(required) else 0.0
    if case.abstention_expected:
        return is_abstention(response.answer) and not cited, citation_validity, 0
    reference = normalize(case.reference_answer)
    answer = normalize(response.answer)
    expected_numbers = numeric_assertions(case.reference_answer or "")
    answer_numbers = numeric_assertions(response.answer)
    unsupported_numbers = answer_numbers - expected_numbers
    content_matches = answer == reference
    citations_complete = required.issubset(cited)
    return (
        content_matches and citations_complete and not unsupported_numbers,
        citation_validity,
        len(unsupported_numbers),
    )


def verify_evidence(
    case: EvaluationCase,
    response: SystemResponse,
    response_role: str,
) -> EvidenceVerificationOutput:
    expected_numbers = numeric_assertions(case.reference_answer or "")
    assertions = []
    for number in sorted(numeric_assertions(response.answer)):
        supported = number in expected_numbers
        kind = "DEADLINE" if "deadline" in case.category or "deadline" in case.tags else "NUMBER"
        assertions.append(
            EvidenceAssertion(
                claim=number,
                supported=supported,
                evidence_ids=list(case.required_evidence) if supported else [],
                assertion_type=kind,
                explanation=(
                    "Numeric assertion appears in the approved reference answer."
                    if supported
                    else "Numeric assertion is absent from the approved reference answer and required evidence."
                ),
            )
        )
    citations_valid = set(response.citations).issubset(set(case.required_evidence))
    return EvidenceVerificationOutput(
        case_id=case.case_key,
        response_role=response_role,
        assertions=assertions,
        citations_valid=citations_valid,
        contradictory_sources=[],
        evidence_complete=citations_valid and all(item.supported for item in assertions),
    )


def compare_case(
    case: EvaluationCase,
    baseline: SystemResponse,
    candidate: SystemResponse,
) -> CaseEvaluation:
    baseline_passed, _, _ = evaluate_response(case, baseline)
    candidate_passed, citation_validity, unsupported = evaluate_response(case, candidate)
    verification = verify_evidence(case, candidate, "CANDIDATE")
    required_count = len(case.required_evidence)
    evidence_coverage = (
        len(set(candidate.citations) & set(case.required_evidence)) / required_count
        if required_count
        else 1.0
    )
    return CaseEvaluation(
        case_id=case.case_key,
        baseline=baseline,
        candidate=candidate,
        baseline_passed=baseline_passed,
        candidate_passed=candidate_passed,
        regression=baseline_passed and not candidate_passed,
        improvement=not baseline_passed and candidate_passed,
        mandatory_failed=case.release_blocking and not candidate_passed,
        citation_validity=citation_validity,
        evidence_coverage=evidence_coverage,
        unsupported_numeric_claims=unsupported,
        risk_weight=case.risk_weight,
        evidence_verification=verification,
    )
