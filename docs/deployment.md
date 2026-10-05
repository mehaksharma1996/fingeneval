# Experimental prototype deployment notes

> **Status:** These notes apply only to the frozen local governance prototype. The supported FinGenEval harness runs offline through Streamlit or the CLI. The cloud table below is an unvalidated mapping, not a deployed environment.

## Local

`docker compose up --build` starts the API with a persistent SQLite volume and the frontend on port 8080. This path is for development and demonstrations.

## Unvalidated AWS service mapping

| Local component | Managed mapping |
|---|---|
| React/nginx | S3 + CloudFront or approved static hosting with WAF |
| FastAPI containers | ECS/Fargate or EKS behind ALB |
| SQLite | RDS PostgreSQL Multi-AZ with encryption, backups, RLS |
| Threaded/eager jobs | SQS + ECS workers, Step Functions, or Temporal |
| Local reports | S3 with versioning, KMS, object lock where required |
| Environment secrets | Secrets Manager with rotation |
| Metrics/logs/traces | ADOT/OpenTelemetry to CloudWatch and security tooling |
| Identity header | Enterprise OIDC/SAML through an identity-aware gateway |

Use private subnets for database/workers, VPC endpoints for managed services, restrictive egress for model providers, separate execution and migration roles, signed images, and per-environment accounts. The Kubernetes reference manifest is intentionally incomplete and must be adapted to the organization's ingress, identity, secret, policy, and monitoring standards.

## Migration and release

Build immutable API/web images, generate an SBOM, scan dependencies and images, run tests, back up the database, run `alembic upgrade head` as a one-off migration job, deploy API/workers, verify readiness, then publish the web assets. `alembic check` must show no model drift. Roll back application images only when the database revision remains compatible; otherwise use a reviewed forward migration.

## Environment controls

Set `FINGENEVAL_LOCAL_AUTH_ENABLED=false`. Supply the database URL and provider credentials from managed secrets. Use PostgreSQL connection pooling. Restrict CORS to the deployed UI. Configure rate, size, concurrency, case-count, token, and cost limits per tenant. Disable Swagger UI externally if the API gateway does not protect it.

## Scalability

Workers claim idempotent case tasks from a durable queue. Partition by run and tenant, batch provider requests where supported, cache content-addressed embeddings within tenant boundaries, persist progress, and apply provider-specific rate limits. Horizontally scale API and workers independently. Archive old immutable results to lower-cost object storage while retaining searchable decision metadata.

No production-scale benchmark has been run. `load/k6-smoke.js` checks readiness under a small local load and must not be presented as capacity evidence.
