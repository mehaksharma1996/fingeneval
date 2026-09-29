# Prioritized next steps

1. **Production identity and tenant enforcement:** integrate OIDC, group-to-role policy, step-up authentication for override, PostgreSQL row-level security, and automated tenant-isolation tests. Depends on the target institution's identity model.
2. **Durable orchestration:** replace local threads with queue leases, heartbeats, distributed cancellation, retry classification, dead-letter handling, and transactional outbox events. Depends on the selected cloud/workflow platform.
3. **Generic authoring:** add project/system/prompt/retrieval/document/dataset CRUD, document ingestion validation, two-person test approval, and version-diff views. The current vertical slice loads a reviewed AML project.
4. **Production evidence stack:** entitlement-aware retrieval, document/version repositories, stale/conflicting-source detection, calibrated NLI/LLM judge, and human-label calibration.
5. **Approval policy depth:** separation of duties, required-role quorum, expiring overrides, accepted-risk expiry, and webhook notifications.
6. **Observability and cost controls:** OpenTelemetry export, worker/provider metrics, per-tenant budgets, queue dashboards, alert policies, and trace sampling without sensitive content.
7. **Storage governance:** S3 adapter, signed report export, retention/legal hold, verified deletion, and tamper-evident audit digest export.
8. **Scale and resilience testing:** PostgreSQL/queue integration tests, provider chaos tests, representative document/case volumes, and published environment-specific measurements.
9. **Safe MCP server:** read-only project/run/finding/status tools and an audited draft-rerun request; no decision override capability.
