# Results

Automated tests execute the synthetic scenario and verify these expected prototype results:

- Initial run: six cases persist with `COMPLETE` status.
- Candidate `2.0-regression`: the SAR deadline case changes 30 to 45 days.
- Evidence verification marks `45` unsupported while retaining the cited source identifier.
- A critical open finding is created with likely failure stage `generation`.
- The deterministic rules produce `BLOCK` and list every trigger.
- A simulated provider failure produces `PARTIAL` and `INSUFFICIENT EVIDENCE`.
- Candidate `2.0-remediated`: targeted rerun passes; the original finding becomes `RESOLVED`; the rerun decision is `PASS`.

These are synthetic workflow tests, not results from a production model or institution.

