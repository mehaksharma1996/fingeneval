"""LLM answer generation for FinGenEval.

This module keeps answer generation separate from retrieval so the platform can
run in retrieval-only mode when no Gemini key is configured. Retrieval-only rows
are never scored with answer-level metrics.
"""

from __future__ import annotations

import argparse
import re
import threading
import time
from dataclasses import dataclass

from .retrievers import RetrievalResult, search
from .settings import settings

MODE_LLM = "llm"
MODE_RETRIEVAL_ONLY = "retrieval_only"
MODE_ERROR = "generation_error"


PROMPT_A_BASIC = """You are a financial policy validation assistant.
Answer the question using only the provided context. Cite evidence with the
bracketed context number, for example [1].

Question:
{question}

Context:
{context}

Answer:
"""


PROMPT_B_STRICT_GOVERNANCE = """You are a financial AI model validation assistant.
Answer only from the provided context and avoid unsupported claims.
If the context does not contain sufficient information, respond exactly with: I cannot determine this from the provided documents.
End every sentence of a supported answer with the bracketed number of the context it relies on, for example [1] or [1][3].
Do not cite context numbers that are not listed below.

Question:
{question}

Context:
{context}

Governance answer:
"""


@dataclass(frozen=True)
class AnswerResult:
    """Generated answer plus mode metadata for evaluation and UI display."""

    answer: str
    prompt_style: str
    mode: str
    latency_seconds: float | None = None
    error: str | None = None

    @property
    def used_api(self) -> bool:
        """Return whether the answer was produced by the LLM."""
        return self.mode == MODE_LLM


class RateLimiter:
    """Enforce a minimum interval between LLM calls.

    # DESIGN: The wait happens before generation timing starts, so rate limiting
    # never shows up as model latency in benchmark results.
    # PRODUCTION: Use a shared token bucket with exponential backoff and jitter.
    """

    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Sleep until the next call is allowed."""
        with self._lock:
            remaining = self._last_call + self.min_interval_seconds - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            self._last_call = time.monotonic()


rate_limiter = RateLimiter(settings.llm_min_interval_seconds)
_client = None


def format_context(results: list[RetrievalResult]) -> str:
    """Format retrieved chunks into a numbered, cited context block."""
    lines = []
    for index, item in enumerate(results, start=1):
        citation = f"{item.source} | {item.section}"
        lines.append(f"[{index}] {citation}\n{item.text}")
    return "\n\n".join(lines)


def build_prompt(question: str, results: list[RetrievalResult], prompt_style: str) -> str:
    """Build the selected prompt template from retrieved evidence."""
    context = format_context(results)
    if prompt_style == "strict_governance":
        return PROMPT_B_STRICT_GOVERNANCE.format(question=question, context=context)
    if prompt_style == "basic":
        return PROMPT_A_BASIC.format(question=question, context=context)
    raise ValueError(f"Unsupported prompt style: {prompt_style}")


def retrieval_only_answer(results: list[RetrievalResult]) -> str:
    """Return a display placeholder when Gemini is not configured.

    This text is shown in the UI only. The evaluator records the row as
    retrieval-only and leaves every answer-level metric empty.
    """
    if not results:
        return "Retrieval-only mode: no evidence was retrieved."
    citations = ", ".join(f"{item.source} ({item.section})" for item in results)
    return (
        "Retrieval-only mode: no GEMINI_API_KEY is configured, so no answer was generated. "
        f"Retrieved evidence: {citations}."
    )


def get_client():
    """Create the Gemini client once per process."""
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def call_gemini(prompt: str) -> str:
    """Call Gemini deterministically and return the generated text."""
    from google.genai import types

    response = get_client().models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        # Plain single-shot generation: no tool calling, so answers come only from the prompt context.
        config=types.GenerateContentConfig(
            temperature=0.0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return (response.text or "").strip()


class DailyQuotaExhausted(RuntimeError):
    """Raised once the provider's per-day quota is used up; retrying cannot help."""


_daily_quota_exhausted = False


def reset_daily_quota_flag() -> None:
    """Allow API calls again at the start of a new run (quotas reset daily)."""
    global _daily_quota_exhausted
    _daily_quota_exhausted = False


def is_daily_quota_error(text: str) -> bool:
    """Detect per-day quota errors, which should stop the run rather than retry."""
    return "PerDay" in text


def is_retryable_error(text: str) -> bool:
    """Per-minute rate limits and temporary overloads are worth retrying."""
    return any(marker in text for marker in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"))


def retry_delay_seconds(text: str, attempt: int) -> float:
    """Use the server's suggested retry delay when given, else exponential backoff."""
    match = re.search(r"retry in ([\d.]+)s|retryDelay'?:\s*'(\d+)s", text)
    if match:
        return min(float(match.group(1) or match.group(2)) + 1.0, 120.0)
    return min(5.0 * 2**attempt, 120.0)


def generate_with_retry(prompt: str) -> tuple[str, float]:
    """Call Gemini with retries and return (text, latency of the successful attempt).

    Retry sleeps are not part of the returned latency.
    """
    global _daily_quota_exhausted
    if _daily_quota_exhausted:
        raise DailyQuotaExhausted("Daily generation quota already exhausted in this process; skipped call.")
    for attempt in range(settings.llm_max_retries + 1):
        rate_limiter.wait()
        start = time.perf_counter()
        try:
            return call_gemini(prompt), time.perf_counter() - start
        except Exception as exc:
            text = str(exc)
            if is_daily_quota_error(text):
                _daily_quota_exhausted = True
                raise
            if attempt == settings.llm_max_retries or not is_retryable_error(text):
                raise
            time.sleep(retry_delay_seconds(text, attempt))
    raise AssertionError("unreachable")


def answer_question(
    question: str,
    results: list[RetrievalResult],
    prompt_style: str = "strict_governance",
) -> AnswerResult:
    """Generate an answer from retrieved context, timing only the model call."""
    if not settings.gemini_api_key:
        return AnswerResult(retrieval_only_answer(results), prompt_style, MODE_RETRIEVAL_ONLY)
    prompt = build_prompt(question, results, prompt_style)
    try:
        answer, latency = generate_with_retry(prompt)
    except Exception as exc:
        message = f"Gemini generation failed; retrieved evidence is still available. Error: {exc}"
        return AnswerResult(message, prompt_style, MODE_ERROR, error=str(exc))
    return AnswerResult(answer, prompt_style, MODE_LLM, latency)


def smoke_test(prompt_style: str = "strict_governance") -> AnswerResult:
    """Run a no-key-safe answer-generation test over BM25 evidence."""
    question = "What is the AML SAR filing deadline?"
    results = search(question, method="bm25", top_k=3)
    return answer_question(question, results, prompt_style=prompt_style)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a FinGenEval answer-generation smoke test.")
    parser.add_argument("--prompt-style", default="strict_governance", choices=["basic", "strict_governance"])
    args = parser.parse_args()
    result = smoke_test(prompt_style=args.prompt_style)
    print(f"prompt_style={result.prompt_style} mode={result.mode} model={settings.gemini_model}")
    print(result.answer)
