"""Streamlit front end for the FinGenEval RAG validation harness.

The app is an evaluation tool: it inspects retrieval evidence, runs the labeled
benchmark, and exports validation reports. It is not a conversational assistant.
"""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from src.evaluator import DEFAULT_METHODS, RetrievalEngine, load_questions, run_evaluation
from src.llm import answer_question
from src.metrics import check_claims
from src.report_generator import (
    generate_governance_report,
    recommended_config,
    summarize_generation,
    summarize_retrieval,
)
from src.settings import settings


PROMPT_STYLES = ["strict_governance", "basic"]


@st.cache_resource
def get_engine() -> RetrievalEngine:
    """Return a cached retrieval engine so indexes are reused across tabs."""
    return RetrievalEngine()


@st.cache_data
def get_questions() -> pd.DataFrame:
    """Load the labeled benchmark questions once."""
    return load_questions()


def render_mode_banner() -> None:
    """State plainly whether answer-level metrics can be produced."""
    if settings.gemini_api_key:
        st.caption(f"Generation model: {settings.gemini_model}")
    else:
        st.warning(
            "No GEMINI_API_KEY is configured. Runs are retrieval-only: retrieval metrics are computed, "
            "answer-level metrics (faithfulness, citations, hallucination, abstention) are not."
        )


def render_evidence(results) -> None:
    """Display retrieved chunks with rank, section, and score."""
    for index, item in enumerate(results, start=1):
        label = f"[{index}] {item.source} | {item.section} | score {item.score:.3f}"
        with st.expander(label, expanded=index == 1):
            st.write(item.text)


def question_picker(key: str) -> str:
    """Pick a labeled benchmark question or enter a custom one."""
    questions = get_questions()["question"].tolist()
    sample = st.selectbox("Benchmark question", questions, key=f"{key}_sample")
    return st.text_input("Question (editable)", value=sample, key=f"{key}_text")


def inspector_tab(engine: RetrievalEngine) -> None:
    """Inspect one query: retrieved evidence, answer, and per-sentence checks."""
    st.caption("Trace a single query through retrieval, generation, and claim-level grounding checks.")
    question = question_picker("inspect")
    col1, col2, col3 = st.columns(3)
    method = col1.selectbox("Retrieval method", DEFAULT_METHODS, index=2)
    prompt_style = col2.selectbox("Prompt style", PROMPT_STYLES)
    top_k = col3.slider("Top k", 1, 10, 3)
    vector_weight = st.slider("Hybrid vector weight (BM25 weight = 1 - value)", 0.0, 1.0, settings.hybrid_vector_weight, 0.05)
    if st.button("Inspect Query", type="primary"):
        results = engine.search(question, method, top_k, vector_weight, 1.0 - vector_weight)
        answer = answer_question(question, results, prompt_style)
        st.subheader("Answer")
        st.write(answer.answer)
        st.caption(f"Mode: {answer.mode}")
        if answer.used_api:
            checks = check_claims(answer.answer, question, results)
            st.subheader("Claim Checks")
            st.dataframe(
                pd.DataFrame(
                    {
                        "sentence": [c.sentence for c in checks],
                        "term_support": [round(c.term_support, 2) for c in checks],
                        "unsupported_numbers": [", ".join(sorted(c.unsupported_numbers)) for c in checks],
                        "cited": [c.cited for c in checks],
                        "invalid_citation": [c.invalid_citation for c in checks],
                        "flagged": [c.flagged for c in checks],
                    }
                ),
                width="stretch",
            )
        st.subheader("Retrieved Evidence")
        render_evidence(results)


def comparison_tab(engine: RetrievalEngine) -> None:
    """Show each retrieval method's ranked evidence for the same question."""
    st.caption("Compare the evidence each retrieval method ranks for one question.")
    question = question_picker("compare")
    top_k = st.slider("Top k", 1, 8, 3, key="compare_k")
    if st.button("Compare Retrieval Methods", type="primary"):
        columns = st.columns(len(DEFAULT_METHODS))
        for column, method in zip(columns, DEFAULT_METHODS):
            with column:
                st.markdown(f"**{method}**")
                for index, item in enumerate(engine.search(question, method, top_k), start=1):
                    st.caption(f"[{index}] {item.source} | {item.section}")


def benchmark_tab(engine: RetrievalEngine) -> None:
    """Run the labeled benchmark and show aggregate metrics."""
    st.caption("Run every labeled question through the selected configurations.")
    methods = st.multiselect("Retrieval methods", DEFAULT_METHODS, default=DEFAULT_METHODS)
    prompts = st.multiselect("Prompt styles", PROMPT_STYLES, default=["strict_governance"])
    top_k = st.slider("Top k", 1, 8, 3, key="bench_k")
    calls = len(get_questions()) * len(methods) * len(prompts)
    if settings.gemini_api_key:
        minutes = calls * settings.llm_min_interval_seconds / 60
        st.info(f"{calls} LLM calls; about {minutes:.0f} minutes at one call every {settings.llm_min_interval_seconds:g}s.")
    if st.button("Run Benchmark", type="primary", disabled=not methods or not prompts):
        with st.spinner("Running benchmark..."):
            frame, metadata = run_evaluation(methods, prompts, top_k, engine)
        st.session_state["eval_df"] = frame
        st.session_state["eval_meta"] = metadata
    frame = st.session_state.get("eval_df", pd.DataFrame())
    if frame.empty:
        return
    render_summaries(frame)
    st.subheader("Per-Row Results")
    st.dataframe(frame, width="stretch")
    st.download_button(
        "Download Evaluation CSV",
        data=frame.to_csv(index=False),
        file_name="fingeneval_evaluation_results.csv",
        mime="text/csv",
    )


def render_summaries(frame: pd.DataFrame) -> None:
    """Render retrieval and answer-quality summaries with charts."""
    retrieval = summarize_retrieval(frame)
    st.subheader("Retrieval Quality (answerable questions)")
    st.dataframe(retrieval, width="stretch")
    long = retrieval.melt(
        id_vars="retrieval_method",
        value_vars=["hit_at_k", "reciprocal_rank", "contextual_precision", "contextual_recall"],
        var_name="metric",
    )
    st.plotly_chart(
        px.bar(long, x="metric", y="value", color="retrieval_method", barmode="group", range_y=[0, 1]),
        width="stretch",
    )
    generation = summarize_generation(frame)
    st.subheader("Answer Quality")
    if generation.empty:
        st.info("Not measured in this run (retrieval-only mode).")
    else:
        st.dataframe(generation, width="stretch")


def report_tab() -> None:
    """Render the deterministic validation report and downloads."""
    st.caption("Deterministic report built only from computed metrics and deployment gates.")
    frame = st.session_state.get("eval_df", pd.DataFrame())
    if frame.empty:
        st.warning("Run the benchmark first to generate a validation report.")
        return
    metadata = st.session_state.get("eval_meta", {})
    st.subheader("Recommended Configuration")
    st.dataframe(pd.DataFrame([recommended_config(frame)]), width="stretch")
    report = generate_governance_report(frame, metadata)
    st.markdown(report)
    col1, col2 = st.columns(2)
    col1.download_button(
        "Download Validation Report (.md)", data=report, file_name="fingeneval_validation_report.md", mime="text/markdown"
    )
    col2.download_button(
        "Download Run Metadata (.json)",
        data=json.dumps(metadata, indent=2),
        file_name="fingeneval_run_metadata.json",
        mime="application/json",
    )


def main() -> None:
    """Launch the FinGenEval validation dashboard."""
    st.set_page_config(page_title="FinGenEval", layout="wide")
    st.title("FinGenEval")
    st.caption("RAG evaluation and validation harness for financial policy Q&A")
    render_mode_banner()
    engine = get_engine()
    tabs = st.tabs(["Query Inspector", "Retrieval Comparison", "Benchmark", "Validation Report"])
    with tabs[0]:
        inspector_tab(engine)
    with tabs[1]:
        comparison_tab(engine)
    with tabs[2]:
        benchmark_tab(engine)
    with tabs[3]:
        report_tab()


if __name__ == "__main__":
    main()
