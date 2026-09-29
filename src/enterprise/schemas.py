"""Typed contracts shared by API, agents, policy rules, and persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReleaseOutcome(StrEnum):
    PASS = "PASS"
    PASS_WITH_CONDITIONS = "PASS_WITH_CONDITIONS"
    BLOCK = "BLOCK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    RETIRED = "RETIRED"


class FindingStatus(StrEnum):
    OPEN = "OPEN"
    IN_REMEDIATION = "IN_REMEDIATION"
    READY_FOR_RERUN = "READY_FOR_RERUN"
    RESOLVED = "RESOLVED"
    ACCEPTED_RISK = "ACCEPTED_RISK"


class ApprovalAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    OVERRIDE = "OVERRIDE"


class Role(StrEnum):
    ADMIN = "ADMIN"
    EVALUATOR = "EVALUATOR"
    COMPLIANCE_REVIEWER = "COMPLIANCE_REVIEWER"
    BUSINESS_OWNER = "BUSINESS_OWNER"
    VIEWER = "VIEWER"


class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    intended_use: str = Field(min_length=20, max_length=4000)
    prohibited_uses: list[str] = Field(min_length=1)
    business_owner: str = Field(min_length=2, max_length=160)
    technical_owner: str = Field(min_length=2, max_length=160)
    risk_tier: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    required_approver_roles: list[Role] = Field(default_factory=lambda: [Role.COMPLIANCE_REVIEWER])


class SystemVersionCreate(BaseModel):
    name: str
    version: str
    kind: Literal["BASELINE", "CANDIDATE"]
    model_provider: str
    model_name: str
    prompt_version: str
    retrieval_config: dict[str, Any]
    tool_config: dict[str, Any] = Field(default_factory=dict)
    data_source_version: str


class EvaluationCaseContract(BaseModel):
    id: str
    title: str
    input_text: str = Field(min_length=5, max_length=4000)
    business_process: str
    category: str
    source_document_ids: list[str]
    expected_behavior: str
    reference_answer: str | None = None
    required_evidence: list[str]
    answerability: Literal["ANSWERABLE", "UNANSWERABLE"]
    severity: Severity
    risk_weight: float = Field(gt=0, le=10)
    release_blocking: bool
    abstention_expected: bool
    freshness_requirement: str | None = None
    mandatory_review_role: Role | None = None
    tags: list[str] = Field(default_factory=list)
    version: int = Field(ge=1)
    status: CaseStatus
    created_by: str
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None

    @field_validator("approved_by")
    @classmethod
    def approved_case_has_approver(cls, value: str | None, info):
        if info.data.get("status") == CaseStatus.APPROVED and not value:
            raise ValueError("approved cases require approved_by")
        return value


class SystemResponse(BaseModel):
    answer: str
    citations: list[str]
    retrieved_evidence: list[str] = Field(default_factory=list)
    retrieval_method: str = "none"
    generation_mode: str = "deterministic"
    latency_ms: float = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    provider_request_id: str


class EvidenceAssertion(BaseModel):
    claim: str
    supported: bool
    evidence_ids: list[str]
    assertion_type: Literal["TEXT", "NUMBER", "DATE", "RATE", "THRESHOLD", "DEADLINE"]
    explanation: str


class EvidenceVerificationOutput(BaseModel):
    case_id: str
    response_role: Literal["BASELINE", "CANDIDATE"]
    assertions: list[EvidenceAssertion]
    citations_valid: bool
    contradictory_sources: list[str] = Field(default_factory=list)
    evidence_complete: bool


class CaseEvaluation(BaseModel):
    case_id: str
    baseline: SystemResponse
    candidate: SystemResponse
    baseline_passed: bool
    candidate_passed: bool
    regression: bool
    improvement: bool
    mandatory_failed: bool
    citation_validity: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    unsupported_numeric_claims: int = Field(ge=0)
    risk_weight: float = Field(gt=0)
    error: str | None = None
    evidence_verification: EvidenceVerificationOutput


class PolicyRuleResult(BaseModel):
    rule_id: str
    description: str
    triggered: bool
    outcome: ReleaseOutcome | None = None
    evidence: list[str] = Field(default_factory=list)


class ReleaseDecisionContract(BaseModel):
    outcome: ReleaseOutcome
    policy_version: str
    rules: list[PolicyRuleResult]
    required_approvals: list[Role]
    rationale: str
    computed_at: datetime = Field(default_factory=utc_now)


class IntakeOutput(BaseModel):
    completeness: Literal["SUFFICIENT", "MISSING_INFORMATION"]
    initial_risk: Severity
    recommendation: Literal["CONTINUE", "CLARIFY", "DEFER", "REJECT"]
    missing_information: list[str]
    rationale: str


class TestProposal(BaseModel):
    title: str
    category: str
    expected_behavior: str
    permitted_evidence_ids: list[str]
    severity: Severity
    release_blocking: bool
    review_status: Literal["DRAFT"] = "DRAFT"


class TestDesignOutput(BaseModel):
    proposals: list[TestProposal]
    source_document_ids: list[str]
    human_approval_required: Literal[True] = True


class RiskGovernanceOutput(BaseModel):
    finding_ids: list[str]
    risk_categories: list[str]
    recommended_severity: Severity
    required_reviewers: list[Role]
    recommendation: ReleaseOutcome
    rationale: str


class InvestigationOutput(BaseModel):
    finding_id: str
    likely_stage: Literal[
        "dataset",
        "ingestion",
        "retrieval",
        "reranking",
        "prompt",
        "generation",
        "citation",
        "tool_use",
        "policy_configuration",
    ]
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]
    remediation: str
    engineering_ticket: str
    rerun_case_ids: list[str]


class HandoffOutput(BaseModel):
    release_outcome: ReleaseOutcome
    architecture_rationale: str
    test_evidence: list[str]
    open_risks: list[str]
    scaling_concerns: list[str]
    owners: dict[str, str]
    monitoring_requirements: list[str]
    rollback_guidance: str
    unresolved_decisions: list[str]


class ApprovalRequest(BaseModel):
    action: ApprovalAction
    justification: str = Field(min_length=20, max_length=4000)


class RemediationRequest(BaseModel):
    description: str = Field(min_length=20, max_length=4000)
    owner_user_id: str


class ErrorContract(BaseModel):
    code: str
    message: str
    correlation_id: str
    details: dict[str, Any] = Field(default_factory=dict)
