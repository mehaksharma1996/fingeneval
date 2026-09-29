# Threat model

## Assets and security objectives

Assets include source policies, evaluation cases, system prompts/configurations, responses, findings, release policies, approvals, audit history, identities, and provider credentials. Primary objectives are tenant confidentiality, release-decision integrity, audit availability, and bounded evaluation cost.

| Threat | Example impact | Current control | Production work |
|---|---|---|---|
| Prompt injection | Uploaded policy tells the evaluator to ignore gates | Document text is data; tools and gates are outside prompts; adversarial pack case | Content disarm/sandbox, injection classifier, signed source allowlist |
| Malicious upload | Parser exploit or executable content | Local vertical slice accepts no uploads | MIME/magic validation, 10 MiB limit, malware scan, isolated parser, deny macros |
| Data poisoning | Stale or modified policy changes expected answer | Versioned approved dataset and content hash | Document signatures, two-person approval, lineage, anomaly review |
| Cross-tenant retrieval | One bank sees another's policy/results | Tenant ID comes from user record; service queries filter tenant; tests cover probing | PostgreSQL RLS, entitlement-aware vector filters, isolation test suite |
| Sensitive-data leakage | Prompts or responses reach logs/provider | Structured logs omit prompt/response content by default | DLP/redaction, private endpoints, provider retention controls, SIEM rules |
| Unauthorized override | Evaluator converts a block to pass | Role check, required justification, computed/effective outcomes separated, audit event | External IAM groups, step-up auth, dual approval for critical cases |
| Audit tampering | Reviewer history is changed | Append-only application behavior and content digests | Immutable/WORM export, chained hashes, restricted DB roles |
| Compromised provider | Fabricated responses or data exfiltration | Provider-neutral boundary, output validation, deterministic offline adapter | Egress allowlist, encryption, multi-provider checks, kill switch |
| Tool abuse | Agent submits a filing or changes policy | No write-capable model tools; tool-permission test; human node | Capability tokens, per-tool policy, transaction approval, sandbox |
| Denial of service | Large datasets exhaust workers/database | Pagination, case isolation, local limits | Quotas, queue admission, autoscaling, circuit breakers, rate limiting |
| Unbounded cost | Recursive/costly model calls | Acyclic graph, fixed retries, deterministic provider, token/cost fields | Per-tenant budgets, reservation, alerts, provider concurrency controls |

## Abuse cases

- A user supplies another tenant's run UUID. The service returns `404` because both ID and tenant must match.
- A provider times out after five of six cases. The run becomes `PARTIAL`; the gate returns `INSUFFICIENT EVIDENCE` regardless of successful cases.
- A generated answer cites the right policy section but invents `45 days`. Evidence verification marks the number unsupported and a release rule blocks it.
- A reviewer overrides a block. The original computed `BLOCK` remains immutable; only the effective outcome changes and the audit records role and justification.

## Residual risk

Local-header identity is not a production authentication mechanism. SQLite offers no row-level security. Audit records are not independently immutable. Upload, webhook, provider-network, and secret-management controls are documented but not fully implemented. A production launch requires security architecture review, penetration testing, privacy review, incident exercises, and dependency/container scanning in the target environment.

