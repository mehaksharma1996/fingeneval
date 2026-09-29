# Scaling plan

Move to PostgreSQL and a durable case-task queue. Store a case lease, attempt, heartbeat, idempotency key, and provider request ID. Scale stateless API and workers independently. Enforce per-tenant and per-provider concurrency/token/cost budgets. Batch embeddings and compatible inference; content-address caches by tenant and version. Use object storage for documents/reports, stream progress from persisted events, and archive immutable audit/results according to retention policy.

Before sizing, benchmark representative document counts, case volumes, providers, and concurrency on named hardware/cloud resources and publish p50/p95/p99, error/retry rate, queue age, throughput, tokens, and cost. The repository makes no tested-scale claim.

