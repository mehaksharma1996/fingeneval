# Experimental governance-prototype patterns

> **Status:** These patterns document the frozen local prototype. They are not the canonical FinGenEval architecture and must not be presented as a multi-agent or production platform.

The enterprise package is intentionally organized around replaceable contracts:

- `ModelProvider.generate(case, system)` isolates hosted/local models.
- `EvaluationCaseContract` carries risk, evidence, approval, and lifecycle metadata.
- `SystemResponse`, `EvidenceVerificationOutput`, and workflow-step schemas validate generated structure.
- `compare_case` is a deterministic evaluation tool; provider output never decides its own correctness.
- `RunFacts -> compute_release_decision` is a pure, versioned policy interface.
- The bounded workflow runner provides timeout, retry, and trace hooks for deterministic helper steps.
- `ServiceActor` and role guards form explicit human-approval nodes.
- `ObjectStorage` separates report creation from local/S3 persistence.
- Trace and audit records keep workflow diagnostics distinct from governance history.

To create another financial pack, add a JSON file with approved cases, retain the same typed fields, register its dataset version, and reuse the provider/evaluation/policy workflow. `data/packs/complaint_handling.json` demonstrates complaint deadlines and unapproved compensation without copying the AML implementation.

Prompt templates from the original harness remain in `src/llm.py`. Production prompts should be immutable registered versions, include evidence/tool boundaries, and be stored by hash rather than copied into logs.

Reference architectures live in `docs/architecture.md` and `docs/deployment.md`. Retry, timeout, idempotency, audit, report, and human-control behavior is tested in `tests/test_enterprise_*`.
