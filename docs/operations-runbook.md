# Experimental governance-prototype operations runbook

> **Status:** Proposed operating notes for the frozen local prototype. The objectives are unvalidated targets and do not describe the supported offline harness or a deployed service.

## Service objectives

Proposed starting objectives, subject to measured production demand: API availability 99.9%, p95 read latency below 500 ms excluding long jobs, no completed decision for a partial run, and 100% of overrides linked to an active user and justification.

## Health and telemetry

- `/health/live` confirms process health.
- `/health/ready` checks database connectivity.
- `/metrics` exposes HTTP counters and latency sums in Prometheus text format.
- Logs include correlation ID, route, status, and duration without prompt/response content.
- Runs carry IDs, status, stage, progress, timestamps, and error summaries.
- Workflow traces persist step, attempt, duration, validated output, and error.

## Common incidents

**Provider outage:** Pause new expensive jobs, let current cases fail closed, confirm runs become `PARTIAL`, inspect provider-error rate, activate circuit breaker, and rerun with the same immutable versions after recovery.

**Queue backlog:** Check oldest queue age, worker heartbeats, provider rate limits, and database locks. Scale workers only within provider and cost budgets. Never mark queued work complete manually.

**Database unavailable:** Readiness must fail. Stop workers from claiming cases. Restore connectivity or fail over, validate migration version, reconcile leases/idempotency keys, and resume.

**Suspected tenant leak:** Disable affected access, preserve logs/audit, rotate credentials, identify exposed objects and provider calls, notify incident/privacy teams, and do not delete evidence outside the approved incident process.

**Unauthorized override:** Lock the identity, retain the approval/audit record, restore the computed gate as the operational decision, review access groups, and investigate all actions by the principal.

## Backup, restore, and retention

Production PostgreSQL needs point-in-time recovery and quarterly restore tests. Object reports require versioning and lifecycle rules. Audit retention must be set with legal/privacy owners. Deletion should enqueue tenant-scoped database/object deletion, record authorization, verify completion, and preserve only legally required tombstone evidence.

## Rollback

Retain the registered baseline configuration and deployment artifact. If release monitors breach policy, route traffic back to the baseline, suspend the candidate, open a finding linked to observed evidence, and run the affected pack before re-release.

## Local recovery

Stop the API, copy `fingeneval.db` and `reports/generated`, restart, call readiness, and inspect the latest runs. Do not delete partial runs; they are audit evidence. For a clean synthetic demo, use a new database path rather than mutating prior history.
