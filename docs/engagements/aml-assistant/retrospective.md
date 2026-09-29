# Retrospective

The highest-value decision was to model release facts and lifecycle before UI breadth. That exposed the existing partial-run problem and made `INSUFFICIENT EVIDENCE` a state rather than report prose. Keeping agents advisory reduced ambiguity: evidence and investigation benefit from structured assistance, while authorization and release rules remain deterministic.

The prototype remains intentionally narrow. Generic authoring and production integrations would have produced more surface area but less confidence in the core decision. The next engagement should validate source ownership, identity/entitlements, and real ground truth before expanding orchestration.
