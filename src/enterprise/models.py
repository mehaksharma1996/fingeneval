"""SQLAlchemy persistence model with tenant ownership on every aggregate."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class IdTimestampMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Tenant(Base, IdTimestampMixin):
    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)


class User(Base, IdTimestampMixin):
    __tablename__ = "users"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)


class Project(Base, IdTimestampMixin):
    __tablename__ = "projects"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    intended_use: Mapped[str] = mapped_column(Text, nullable=False)
    prohibited_uses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    business_owner: Mapped[str] = mapped_column(String(160), nullable=False)
    technical_owner: Mapped[str] = mapped_column(String(160), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    required_approver_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)


class RegisteredAISystem(Base, IdTimestampMixin):
    __tablename__ = "registered_ai_systems"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(160), nullable=False)


class PromptVersion(Base, IdTimestampMixin):
    __tablename__ = "prompt_versions"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    template_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class RetrievalConfiguration(Base, IdTimestampMixin):
    __tablename__ = "retrieval_configurations"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class DataSource(Base, IdTimestampMixin):
    __tablename__ = "data_sources"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    access_policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class Document(Base, IdTimestampMixin):
    __tablename__ = "documents"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    data_source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"), index=True, nullable=False)
    external_key: Mapped[str] = mapped_column(String(240), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "external_key"),)


class DocumentVersion(Base, IdTimestampMixin):
    __tablename__ = "document_versions"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    __table_args__ = (UniqueConstraint("document_id", "version"),)


class SystemVersion(Base, IdTimestampMixin):
    __tablename__ = "system_versions"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    registered_system_id: Mapped[str] = mapped_column(ForeignKey("registered_ai_systems.id"), nullable=False)
    prompt_version_id: Mapped[str] = mapped_column(ForeignKey("prompt_versions.id"), nullable=False)
    retrieval_configuration_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_configurations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    retrieval_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    tool_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    data_source_version: Mapped[str] = mapped_column(String(80), nullable=False)


class DatasetVersion(Base, IdTimestampMixin):
    __tablename__ = "dataset_versions"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="APPROVED", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationCase(Base, IdTimestampMixin):
    __tablename__ = "evaluation_cases"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.id"), index=True, nullable=False
    )
    case_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    business_process: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    source_document_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    expected_behavior: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str | None] = mapped_column(Text)
    required_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    answerability: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_weight: Mapped[float] = mapped_column(Float, nullable=False)
    release_blocking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    abstention_expected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    freshness_requirement: Mapped[str | None] = mapped_column(String(160))
    mandatory_review_role: Mapped[str | None] = mapped_column(String(40))
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("dataset_version_id", "case_key", "version"),)


class ReleasePolicy(Base, IdTimestampMixin):
    __tablename__ = "release_policies"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EvaluationRun(Base, IdTimestampMixin):
    __tablename__ = "evaluation_runs"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    baseline_system_version_id: Mapped[str] = mapped_column(ForeignKey("system_versions.id"), nullable=False)
    candidate_system_version_id: Mapped[str] = mapped_column(ForeignKey("system_versions.id"), nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), nullable=False)
    release_policy_id: Mapped[str] = mapped_column(ForeignKey("release_policies.id"), nullable=False)
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_runs.id"))
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_case_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key"),)


class CaseResult(Base, IdTimestampMixin):
    __tablename__ = "case_results"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(ForeignKey("evaluation_cases.id"), nullable=False)
    baseline_response: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    candidate_response: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    baseline_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    candidate_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    regression: Mapped[bool] = mapped_column(Boolean, nullable=False)
    improvement: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mandatory_failed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("run_id", "case_id"),)


class MetricResult(Base, IdTimestampMixin):
    __tablename__ = "metric_results"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True, nullable=False)
    case_result_id: Mapped[str] = mapped_column(ForeignKey("case_results.id"), index=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    __table_args__ = (UniqueConstraint("case_result_id", "metric_name"),)


class Finding(Base, IdTimestampMixin):
    __tablename__ = "findings"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True, nullable=False)
    case_result_id: Mapped[str] = mapped_column(ForeignKey("case_results.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    likely_failure_stage: Mapped[str] = mapped_column(String(60), nullable=False)
    recommended_remediation: Mapped[str] = mapped_column(Text, nullable=False)


class Remediation(Base, IdTimestampMixin):
    __tablename__ = "remediations"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PLANNED", nullable=False)
    rerun_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_runs.id"))


class ReleaseDecision(Base, IdTimestampMixin):
    __tablename__ = "release_decisions"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), unique=True, nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    required_approvals: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    effective_outcome: Mapped[str] = mapped_column(String(40), nullable=False)


class HumanApproval(Base, IdTimestampMixin):
    __tablename__ = "human_approvals"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    decision_id: Mapped[str] = mapped_column(ForeignKey("release_decisions.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_role: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)


class ReleaseOverride(Base, IdTimestampMixin):
    __tablename__ = "release_overrides"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    decision_id: Mapped[str] = mapped_column(ForeignKey("release_decisions.id"), index=True, nullable=False)
    approval_id: Mapped[str] = mapped_column(ForeignKey("human_approvals.id"), unique=True, nullable=False)
    original_outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base, IdTimestampMixin):
    __tablename__ = "audit_events"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    correlation_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AgentTrace(Base, IdTimestampMixin):
    __tablename__ = "agent_traces"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class GeneratedReport(Base, IdTimestampMixin):
    __tablename__ = "generated_reports"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
