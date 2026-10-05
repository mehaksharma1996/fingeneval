# Metric calibration protocol

## Purpose

The lexical metrics in FinGenEval are transparent proxies, not semantic ground truth. This protocol measures their agreement with human judgment before anyone changes a threshold or relies on answer-quality gates for a consequential decision.

The v1 packet is intentionally marked `PENDING_HUMAN_REVIEW`. Its cases and candidate answers were assembled programmatically and by AI assistance; they are **not** human labels. The analyzer withholds precision, recall, confidence intervals, and threshold recommendations until required labels are adjudicated.

## Review procedure

Two passes are recommended. A domain reviewer completes the five `human_*` columns using `1`, `0`, or blank only where the label is not applicable. A second reviewer checks disagreements and changes `review_status` to `adjudicated`. If only one reviewer is available, that reviewer may adjudicate, but the limitation must be recorded in `adjudication_notes`.

For each row:

1. Read the question, candidate answer, reference answer, and the full text of every `retrieved_sections` entry in `data/docs/`.
2. Label `human_retrieval_sufficient=1` only when the retrieved text contains all facts needed for the reference answer.
3. Label `human_faithful=1` only when every material candidate-answer claim is entailed by the retrieved text. Treat reversed obligations, negation, wrong numbers, and unsupported exceptions as unfaithful.
4. Label `human_citations_valid=1` only when every material claim has a citation and each citation points to retrieved text that supports that claim.
5. Label `human_answer_correct=1` only when the answer materially matches the reference and does not omit a required condition.
6. Label `human_abstention_correct=1` only when the answer abstains exactly for an unanswerable question and does not abstain for an answerable question.
7. Record a stable non-sensitive `reviewer_id`, an ISO-8601 UTC timestamp, rationale for edge cases, and `review_status=adjudicated` after resolution.
8. After the reviewed CSV is final, replace `annotation_sha256_12=PENDING` in the manifest with the first twelve hexadecimal characters of the file's SHA-256 digest. An adjudicated but unsealed packet is rejected.

Blank labels are allowed only where the analyzer considers a metric not applicable: retrieval and answer correctness on unanswerable questions, and faithfulness/citation validity for an abstention with no claims. The analyzer rejects missing required labels, missing reviewer provenance, invalid section identifiers, dataset drift, and unapproved threshold changes.

## Run the analysis

```powershell
python -m src.calibration
```

Exit code `2` and status `PENDING_HUMAN_REVIEW` are expected before adjudication. No calibration performance figures are emitted. Exit code `0` is possible only after the complete packet passes the fail-closed review checks.

## Threshold and judge governance

Thresholds live in `data/calibration/v1/manifest.json`. A changed threshold requires `threshold_change.approved_by`, `approved_at_utc`, `evidence_report`, and `reason`; otherwise analysis fails.

Optional probabilistic judges must record their model/provider/prompt configuration and per-case success or failure. They remain advisory. A failed, unavailable, or unconfigured judge never becomes a score and never substitutes for human labels or deterministic policy.

## Interpretation

The calibrated report includes confusion counts, precision, recall, F1, accuracy with Wilson 95% intervals, and false-positive/false-negative case identifiers by question type. With only twelve v1 cases, intervals will be wide. This packet is a control test for known lexical failure modes, not proof of production validity; expand it with independently sampled real outputs before any consequential use.
