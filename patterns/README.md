# Reusable validation patterns

The enterprise package is intentionally organized around replaceable contracts:

- `ModelProvider.generate(case, system)` isolates hosted/local models.
- `EvaluationCaseContract` carries risk, evidence, approval, and lifecycle metadata.
- `SystemResponse`, `EvidenceVerificationOutput`, and agent output schemas validate all generated structure.
- `compare_case` is a deterministic evaluation tool; provider output never decides its own correctness.
- `RunFacts -> compute_release_decision` is a pure, versioned policy interface.
- `ControlledAgentRunner` provides bounded timeout/retry and trace hooks without recursive delegation.
- `ServiceActor` and role guards form explicit human-approval nodes.
- `ObjectStorage` separates report creation from local/S3 persistence.
- `AgentTrace` and `AuditEvent` helpers keep operational traces distinct from governance history.

To create another financial pack, add a JSON file with approved cases, retain the same typed fields, register its dataset version, and reuse the provider/evaluation/policy workflow. `data/packs/complaint_handling.json` demonstrates complaint deadlines and unapproved compensation without copying the AML implementation.

Prompt templates from the original harness remain in `src/llm.py`. Production prompts should be immutable registered versions, include evidence/tool boundaries, and be stored by hash rather than copied into logs.

Reference architectures live in `docs/architecture.md` and `docs/deployment.md`. Retry, timeout, idempotency, audit, report, and human-control behavior is tested in `tests/test_enterprise_*`.

