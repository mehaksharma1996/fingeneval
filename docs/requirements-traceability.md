# Requirements traceability

| Capability | Evidence in repository | Current boundary |
|---|---|---|
| Production GenAI engineering | Provider interface, deterministic adapter, Gemini boundary, typed outputs, retries/timeouts, token/cost fields | Real provider enterprise adapter needs approval/configuration |
| RAG and evaluation | Preserved BM25/vector/hybrid/reranker, 45-question corpus, claim/citation metrics, two reusable packs | Semantic judges and production-scale corpus need calibration |
| Agent orchestration | Explicit typed intake, design, verification, risk, investigation, handoff nodes with traces | Acyclic local runner; durable workflow adapter pending |
| Deterministic governance | Versioned policy, specific rules/evidence, four outcomes, override separation | Organization-specific policy authoring UI pending |
| Full-stack | FastAPI/OpenAPI, SQLAlchemy/Alembic, React/TypeScript workflow | Generic authoring is incomplete |
| Data engineering | Version/hash lineage, immutable case results, local/object storage adapters | Document-version ingestion and warehouse export pending |
| Cloud/DevOps | Docker, Compose, Kubernetes reference, AWS mapping, CI, migrations | No external deployment or paid resource created |
| Observability | JSON request logs, correlation/run IDs, persisted agent traces, Prometheus endpoint | OpenTelemetry exporter and dashboards pending |
| Security/privacy | Role checks, tenant filters, audit, secret placeholders, threat model, scans | Local header auth and SQLite are development-only |
| Responsible AI | Intended/prohibited use, oversight, limitations, provider/data risk | Requires institution-specific assessment |
| Forward-deployed qualification | AML engagement discovery, scorecard, constraints, kill/continue, handoff | Evidence is synthetic and local |
| Reusable patterns | Interfaces, schemas, tool/policy contracts, two financial packs | Complaint pack demonstrates structure; full run fixture can be expanded |
| Handoff quality | Report digest, architecture, runbook, rollback, owners, next steps | Tamper-evident external archive pending |

