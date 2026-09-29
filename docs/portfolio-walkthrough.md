# Portfolio walkthrough (7 minutes)

**0:00 — Business problem.** Open the dashboard. Explain that average AI quality can rise while a single mandatory deadline regresses. The release unit is an evidence-backed comparison, not a chatbot score.

**0:45 — Scope and registry.** Show intended/prohibited use, owners, critical risk tier, baseline/candidate versions, prompt/retrieval/tool configuration, approved dataset, and policy version.

**1:45 — Run.** Start the baseline comparison. Point out persisted progress, explicit `COMPLETE/PARTIAL/FAILED/CANCELLED` states, separate case records, latency/cost fields, and agent traces. No paid credential is used.

**2:30 — Critical regression.** Open the finding. The baseline says 30 days; the candidate says 45. Show expected behavior and `aml_transaction_monitoring_policy.md#SAR Filing Timelines`. Explain that the citation itself is plausible, but the numeric assertion is unsupported.

**3:30 — Release rule.** Open the decision. `NO_CRITICAL_REGRESSIONS`, `MANDATORY_COMPLIANCE_CASES`, `UNSUPPORTED_NUMERIC_CLAIMS`, and the risk-weighted drop trigger `BLOCK`. The gate is deterministic and independent of agent recommendations.

**4:30 — Human control.** Record a synthetic reviewer action. The computed `BLOCK` remains; an authorized override changes only the effective outcome and requires justification. Show the audit timeline.

**5:15 — Remediation.** Record remediation and run only the failed case against immutable candidate `2.0-remediated`. The finding resolves and the targeted run produces `PASS`.

**6:00 — Handoff.** Generate the Markdown report and show its SHA-256 record, open risks, monitoring, ownership, and rollback. Mention local/provider limitations candidly.

**6:40 — Engineering depth.** Point to typed schemas, provider/retriever/policy interfaces, SQLite/PostgreSQL abstraction, FastAPI/OpenAPI, React/TypeScript, end-to-end and failure tests, migrations, containers, CI/security scans, threat model, and reusable complaint pack.

