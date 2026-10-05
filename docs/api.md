# Experimental governance-prototype API

> **Status:** This API is retained as a local experimental consumer of the FinGenEval assets. It is not the supported offline-harness entry point and is not evidence of a production or multi-agent deployment.

Interactive OpenAPI documentation is served at `/docs`; the machine-readable schema is `/openapi.json`. All business endpoints are versioned under `/api/v1`.

Local development authenticates with `X-User-Id`, returned by `POST /api/v1/demo/bootstrap`. The server resolves tenant and role from that user row. Never accept a tenant ID from a caller. Production must replace this boundary with verified enterprise identity claims.

| Method | Path | Role/purpose |
|---|---|---|
| `POST` | `/api/v1/demo/bootstrap` | Local-only synthetic project and users |
| `GET` | `/api/v1/dashboard` | Any active tenant user |
| `GET` | `/api/v1/projects?limit=&offset=&name=` | Paginated tenant projects |
| `POST` | `/api/v1/projects/{id}/runs` | Evaluator/admin; requires `Idempotency-Key` |
| `GET` | `/api/v1/runs/{id}` | Tenant run, cases, findings, decision, traces, audit |
| `POST` | `/api/v1/runs/{id}/cancel` | Evaluator/admin |
| `POST` | `/api/v1/release-decisions/{id}/reviews` | Authorized review; override restricted |
| `POST` | `/api/v1/findings/{id}/remediate-and-rerun` | Evaluator/admin; creates immutable candidate version |
| `POST` | `/api/v1/runs/{id}/reports` | Evaluator/reviewer/admin |

Run creation is idempotent within a tenant. Eager local mode completes before the 202 response; threaded mode returns queued state and clients poll `GET /runs/{id}`. Production should add server-sent events and signed completion webhooks backed by an outbox.

Errors use `{code, message, correlation_id, details}`. Cross-tenant and unknown identifiers both return `404` to reduce resource probing. Validation returns `422`; missing/invalid identity `401`; insufficient role `403`; lifecycle conflict `409`.
