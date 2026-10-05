"""Deterministic governance reporting for FinGenEval evaluation results.

The report is built only from computed metrics. It never uses LLM-generated
text, so every statement can be traced back to the evaluation DataFrame.
"""

from __future__ import annotations

import math

import pandas as pd

from .llm import MODE_ERROR, MODE_LLM
from .run_integrity import RunIntegrity, inspect_run
from .settings import settings

RETRIEVAL_METRICS = [
    "hit_at_k",
    "reciprocal_rank",
    "contextual_precision",
    "contextual_recall",
    "section_recall",
]
CONFIG_KEYS = ["retrieval_method", "prompt_style"]


def pct(value: float) -> str:
    """Format a ratio as a percentage, or n/a when it was not measured."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{100 * float(value):.1f}%"


def ms(value: float) -> str:
    """Format seconds as milliseconds, or n/a when it was not measured."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{1000 * float(value):.1f} ms"


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavored Markdown table."""
    header = "| " + " | ".join(str(column) for column in frame.columns) + " |"
    divider = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, divider, *rows])


def summarize_retrieval(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate retrieval quality on answerable questions and latency on all rows."""
    answerable = frame[frame["answerable"] == 1]
    quality = answerable.groupby("retrieval_method")[RETRIEVAL_METRICS].mean()
    latency = frame.groupby("retrieval_method")["retrieval_latency_seconds"]
    quality["retrieval_p50_s"] = latency.median()
    quality["retrieval_p95_s"] = latency.quantile(0.95)
    quality = quality.reset_index()
    return quality.sort_values(
        ["reciprocal_rank", "contextual_recall", "contextual_precision", "retrieval_p50_s"],
        ascending=[False, False, False, True],
    )


def summarize_generation(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate answer-level metrics per configuration from real LLM rows only."""
    rows = []
    for (method, prompt), group in frame.groupby(CONFIG_KEYS):
        llm = group[group["generation_mode"] == MODE_LLM]
        if llm.empty:
            continue
        answerable = llm[llm["answerable"] == 1]
        unanswerable = llm[llm["answerable"] == 0]
        rows.append(
            {
                "retrieval_method": method,
                "prompt_style": prompt,
                "answered_rows": len(llm),
                "total_rows": len(group),
                "contextual_recall": group.loc[group["answerable"] == 1, "contextual_recall"].mean(),
                "faithfulness_proxy": answerable["faithfulness_proxy"].mean(),
                "citation_coverage": answerable["citation_coverage"].mean(),
                "citation_validity": answerable["citation_validity"].mean(),
                "hallucination_risk": answerable["hallucination_risk"].mean(),
                "answer_correctness_proxy": answerable["answer_correctness_proxy"].mean(),
                "correct_abstention_rate": unanswerable["abstained"].mean(),
                "false_refusal_rate": answerable["abstained"].mean(),
                "unanswerable_hallucination_rate": unanswerable["hallucination_risk"].mean(),
                "generation_error_rate": (group["generation_mode"] == MODE_ERROR).mean(),
                "generation_p50_s": llm["generation_latency_seconds"].median(),
                "generation_p95_s": llm["generation_latency_seconds"].quantile(0.95),
            }
        )
    if not rows:
        return pd.DataFrame()
    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["hallucination_risk", "faithfulness_proxy", "correct_abstention_rate", "contextual_recall"],
        ascending=[True, False, False, False],
        na_position="last",
    )


def gate_results(config: pd.Series) -> list[tuple[str, str, bool]]:
    """Evaluate one configuration against the deployment gates in settings."""

    def at_least(value: float, threshold: float) -> bool:
        return not math.isnan(value) and value >= threshold

    def at_most(value: float, threshold: float) -> bool:
        return not math.isnan(value) and value <= threshold

    s = settings
    return [
        (
            "Contextual recall",
            f">= {pct(s.gate_min_contextual_recall)}",
            at_least(config["contextual_recall"], s.gate_min_contextual_recall),
        ),
        (
            "Faithfulness proxy",
            f">= {pct(s.gate_min_faithfulness)}",
            at_least(config["faithfulness_proxy"], s.gate_min_faithfulness),
        ),
        (
            "Hallucination risk (answerable)",
            f"<= {pct(s.gate_max_hallucination_risk)}",
            at_most(config["hallucination_risk"], s.gate_max_hallucination_risk),
        ),
        (
            "Citation coverage",
            f">= {pct(s.gate_min_citation_coverage)}",
            at_least(config["citation_coverage"], s.gate_min_citation_coverage),
        ),
        (
            "Correct abstention (unanswerable)",
            f">= {pct(s.gate_min_correct_abstention)}",
            at_least(config["correct_abstention_rate"], s.gate_min_correct_abstention),
        ),
        (
            "False refusal (answerable)",
            f"<= {pct(s.gate_max_false_refusal)}",
            at_most(config["false_refusal_rate"], s.gate_max_false_refusal),
        ),
        (
            "Generation error rate",
            f"<= {pct(s.gate_max_generation_error_rate)}",
            at_most(config["generation_error_rate"], s.gate_max_generation_error_rate),
        ),
    ]


def deployment_recommendation(generation: pd.DataFrame, integrity: RunIntegrity) -> str:
    """Apply deterministic model-risk deployment logic to the best configuration."""
    if not integrity.structurally_complete:
        return (
            "Insufficient evidence. The run failed structural integrity validation: "
            + "; ".join(integrity.errors)
            + "."
        )
    if not integrity.deployable_evidence:
        return (
            f"Insufficient evidence. Run status is `{integrity.status}` with generation modes "
            f"{integrity.generation_modes}. A deployment recommendation requires a structurally complete "
            "run in which every benchmark row has a successful LLM answer."
        )
    if generation.empty:
        return (
            "Insufficient evidence. No LLM answers were generated in this run (retrieval-only mode), "
            "so faithfulness, citation, hallucination, and abstention were not measured. "
            "Retrieval results alone cannot support a deployment decision."
        )
    best = generation.iloc[0]
    if best["generation_error_rate"] > settings.gate_max_generation_error_rate:
        return f"Insufficient evidence. Generation failed on {pct(best['generation_error_rate'])} of rows; rerun before deciding."
    if not best["contextual_recall"] >= settings.gate_min_contextual_recall:
        return "Recommend against production deployment: retrieval does not reliably surface the required evidence."
    failed = [name for name, _, passed in gate_results(best) if not passed]
    if failed:
        return (
            "High risk. Do not deploy without remediation and human review. Failed gates: "
            + ", ".join(failed)
            + "."
        )
    return "All gates passed. Recommend a limited internal pilot with human review."


def retrieval_section(frame: pd.DataFrame) -> list[str]:
    """Render retrieval benchmark tables."""
    summary = summarize_retrieval(frame)
    table = pd.DataFrame(
        {
            "Method": summary["retrieval_method"],
            "Hit@k": summary["hit_at_k"].map(pct),
            "MRR": summary["reciprocal_rank"].map(lambda v: f"{v:.3f}"),
            "Contextual precision": summary["contextual_precision"].map(pct),
            "Contextual recall": summary["contextual_recall"].map(pct),
            "Section recall": summary["section_recall"].map(pct),
            "Retrieval p50": summary["retrieval_p50_s"].map(ms),
            "Retrieval p95": summary["retrieval_p95_s"].map(ms),
        }
    )
    answerable = frame[frame["answerable"] == 1]
    by_type = answerable.pivot_table(
        index="question_type", columns="retrieval_method", values="reciprocal_rank", aggfunc="mean"
    )
    counts = answerable.groupby("question_type")["question"].nunique()
    by_type = by_type.map(lambda v: f"{v:.3f}")
    by_type.insert(0, "questions", counts)
    by_type = by_type.reset_index().rename(columns={"question_type": "Question type"})
    return [
        "## Retrieval Benchmark",
        "Measured on answerable questions against labeled relevant sections. Latency excludes model loading "
        "(models are warmed up before timing).",
        markdown_table(table),
        "### MRR By Question Type",
        markdown_table(by_type),
    ]


def generation_section(generation: pd.DataFrame, integrity: RunIntegrity) -> list[str]:
    """Render answer-level metrics or state clearly that none were produced."""
    if generation.empty:
        return [
            "## Answer Quality",
            "Not measured: this run used retrieval-only mode (no GEMINI_API_KEY), so no answers were generated.",
        ]
    table = pd.DataFrame(
        {
            "Configuration": generation["retrieval_method"] + " / " + generation["prompt_style"],
            "Answered": generation["answered_rows"].astype(str) + "/" + generation["total_rows"].astype(str),
            "Faithfulness": generation["faithfulness_proxy"].map(pct),
            "Citation coverage": generation["citation_coverage"].map(pct),
            "Citation validity": generation["citation_validity"].map(pct),
            "Hallucination risk": generation["hallucination_risk"].map(pct),
            "Correct abstention": generation["correct_abstention_rate"].map(pct),
            "False refusal": generation["false_refusal_rate"].map(pct),
            "Answer correctness": generation["answer_correctness_proxy"].map(pct),
            "Gen p50": generation["generation_p50_s"].map(ms),
            "Gen p95": generation["generation_p95_s"].map(ms),
            "Errors": generation["generation_error_rate"].map(pct),
        }
    )
    best = generation.iloc[0]
    gates = pd.DataFrame(
        [(name, threshold, "PASS" if passed else "FAIL") for name, threshold, passed in gate_results(best)],
        columns=["Gate", "Threshold", "Result"],
    )
    evidence_note = (
        "All expected answer rows were generated successfully."
        if integrity.deployable_evidence
        else f"Diagnostic only: run status is `{integrity.status}`; incomplete answer metrics cannot support deployment."
    )
    gate_heading = "Deployment Gates" if integrity.deployable_evidence else "Diagnostic Gate Results"
    return [
        "## Answer Quality",
        evidence_note + " Metrics use only rows where the LLM produced an answer (see Answered). "
        "Generation latency excludes rate-limit and retry waits.",
        markdown_table(table),
        f"### {gate_heading} For `{best['retrieval_method']} / {best['prompt_style']}`",
        markdown_table(gates),
    ]


def metadata_section(
    metadata: dict[str, object] | None, frame: pd.DataFrame, integrity: RunIntegrity
) -> list[str]:
    """Render run metadata so the report identifies exactly what was tested."""
    metadata = metadata or {}
    lines = [
        f"- Run status: {integrity.status}",
        f"- Structural completeness: {integrity.structurally_complete}; "
        f"rows: {integrity.actual_rows}/{integrity.expected_rows}; "
        f"deployment evidence: {integrity.deployable_evidence}",
        f"- Replayed successful LLM rows: {integrity.replayed_rows}",
        f"- Run timestamp (UTC): {metadata.get('run_timestamp_utc', 'unknown')}",
        f"- Dataset: {metadata.get('dataset_path', 'unknown')} (sha256 {metadata.get('dataset_sha256_12', 'unknown')})",
        f"- Questions: {frame['question'].nunique()} "
        f"({int(frame.loc[frame['answerable'] == 1, 'question'].nunique())} answerable, "
        f"{int(frame.loc[frame['answerable'] == 0, 'question'].nunique())} unanswerable)",
        f"- Retrieval methods: {', '.join(sorted(frame['retrieval_method'].unique()))}; top_k = {metadata.get('top_k', 'unknown')}",
        f"- Generation modes: {frame['generation_mode'].value_counts().to_dict()}",
        f"- Generation model: {metadata.get('generation_model') or 'none (retrieval-only)'}",
        f"- Embedding model: {metadata.get('embedding_model', 'unknown')}; reranker: {metadata.get('reranker_model', 'unknown')}",
    ]
    return ["## Run Metadata", "\n".join(lines)]


def generate_governance_report(frame: pd.DataFrame, metadata: dict[str, object] | None = None) -> str:
    """Generate a formal validation report from computed metrics without an LLM."""
    if frame.empty:
        return "No evaluation results are available. Run the evaluation before generating a report."
    metadata = metadata or {}
    integrity = inspect_run(frame, metadata, verify_dataset=False)
    retrieval = summarize_retrieval(frame)
    generation = summarize_generation(frame)
    best_retrieval = retrieval.iloc[0]["retrieval_method"]
    if generation.empty:
        summary = (
            f"Run status: `{integrity.status}`. Best retrieval method by MRR: `{best_retrieval}`. "
            "Answer-level metrics were not produced in this run."
        )
    elif integrity.deployable_evidence:
        best = generation.iloc[0]
        summary = (
            f"Run status: `{integrity.status}`. Best retrieval method by MRR: `{best_retrieval}`. "
            "Best end-to-end configuration: "
            f"`{best['retrieval_method']} / {best['prompt_style']}` "
            f"(hallucination risk {pct(best['hallucination_risk'])}, faithfulness {pct(best['faithfulness_proxy'])}, "
            f"correct abstention {pct(best['correct_abstention_rate'])})."
        )
    else:
        answered = int(generation["answered_rows"].sum())
        total = int(generation["total_rows"].sum())
        summary = (
            f"Run status: `{integrity.status}`. Best retrieval method by MRR: `{best_retrieval}`. "
            f"Answer metrics cover only {answered}/{total} rows and are diagnostic only; no end-to-end "
            "configuration or deployment decision is recommended."
        )
    return "\n\n".join(
        [
            "# FinGenEval Validation Report",
            "## Executive Summary",
            summary,
            *metadata_section(metadata, frame, integrity),
            *retrieval_section(frame),
            *generation_section(generation, integrity),
            "## Metric Definitions",
            "\n".join(
                [
                    "- Hit@k / MRR / contextual precision: computed from labeled relevant sections; precision is rank-weighted (mean precision@k at each relevant rank).",
                    "- Contextual recall: share of labeled evidence facts present in the retrieved context. Section recall: share of labeled relevant sections retrieved.",
                    "- Faithfulness proxy: share of answer sentences whose content terms (>= 60%) and all numbers appear in the retrieved context.",
                    "- Citation coverage: share of answer sentences with a citation. Citation validity: share of cited sentences citing only retrieved evidence.",
                    "- Hallucination risk: answerable questions, share of sentences that are unsupported or cite non-retrieved evidence; unanswerable questions, 1 unless the system abstains.",
                    "- Answer correctness proxy: share of reference-answer terms present in the answer.",
                ]
            ),
            "## Risks And Limitations",
            (
                "The validation corpus is synthetic and small, and answer metrics are lexical proxies that do not "
                "detect negation errors or subtle paraphrase drift. Retrieval quality has not been tested against "
                "production document scale, access controls, or adversarial prompts. Human review remains required "
                "before any customer-impacting deployment."
            ),
            "## Deployment Recommendation",
            deployment_recommendation(generation, integrity),
        ]
    )


def recommended_config(frame: pd.DataFrame, metadata: dict[str, object] | None = None) -> dict[str, object]:
    """Return the best configuration for app display."""
    if frame.empty:
        return {}
    integrity = inspect_run(frame, metadata or {}, verify_dataset=False)
    generation = summarize_generation(frame)
    if integrity.deployable_evidence and not generation.empty:
        result = generation.iloc[0].to_dict()
        result["run_status"] = integrity.status
        return result
    retrieval = summarize_retrieval(frame).iloc[0].to_dict()
    retrieval.update(
        {
            "run_status": integrity.status,
            "recommendation": "INSUFFICIENT_EVIDENCE",
        }
    )
    return retrieval
