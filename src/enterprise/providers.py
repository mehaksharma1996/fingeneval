"""Provider-neutral response interface with a deterministic credential-free adapter."""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..retrievers import BM25Retriever, RetrievalResult, build_chunks
from .models import EvaluationCase, SystemVersion
from .schemas import SystemResponse


class ProviderError(RuntimeError):
    pass


class ModelProvider(ABC):
    @abstractmethod
    def generate(self, case: EvaluationCase, system: SystemVersion) -> SystemResponse:
        """Return one response or raise ProviderError."""


@dataclass
class DeterministicProvider(ModelProvider):
    """Credential-free RAG adapter used by local demos and tests.

    Every response first retrieves real chunks from ``data/docs``. The local
    generation step remains deterministic so the complete release workflow can
    run without paid credentials. Candidate version ``2.0-regression`` then
    intentionally changes the mandatory SAR deadline to 45 days; version
    ``2.0-remediated`` returns the approved answer.
    """

    fail_case_ids: frozenset[str] = frozenset()
    _retrievers: dict[tuple[str, ...], BM25Retriever] = field(default_factory=dict, init=False, repr=False)

    def _search(self, case: EvaluationCase, system: SystemVersion) -> list[RetrievalResult]:
        config = system.retrieval_config or {}
        method = config.get("method", "bm25")
        if method != "bm25":
            raise ProviderError(
                f"enterprise local provider supports retrieval method 'bm25', received {method!r}"
            )
        allowed_sources = tuple(
            sorted(
                set(case.source_document_ids)
                | {evidence.split("#", 1)[0] for evidence in case.required_evidence}
            )
        )
        if not allowed_sources:
            return []
        if allowed_sources not in self._retrievers:
            chunks = [chunk for chunk in build_chunks() if chunk.source in allowed_sources]
            if not chunks:
                raise ProviderError("evaluation case has no indexed approved source documents")
            self._retrievers[allowed_sources] = BM25Retriever(chunks)
        top_k = int(config.get("top_k", 3))
        if top_k < 1 or top_k > 20:
            raise ProviderError("retrieval top_k must be between 1 and 20")
        return self._retrievers[allowed_sources].search(case.input_text, top_k)

    @staticmethod
    def _evidence_id(result: RetrievalResult) -> str:
        return f"{result.source}#{result.section}"

    def generate(self, case: EvaluationCase, system: SystemVersion) -> SystemResponse:
        if case.case_key in self.fail_case_ids:
            raise ProviderError(f"simulated provider timeout for {case.case_key}")
        started = time.perf_counter()
        retrieved = self._search(case, system)
        retrieved_evidence = [self._evidence_id(item) for item in retrieved]
        available_required_evidence = [
            evidence for evidence in case.required_evidence if evidence in retrieved_evidence
        ]
        if case.abstention_expected:
            answer = "I cannot determine this from the approved documents or perform that action."
            citations: list[str] = []
        elif not set(case.required_evidence).issubset(retrieved_evidence):
            answer = "I cannot determine this from the retrieved approved documents."
            citations = available_required_evidence
        elif case.case_key == "aml-sar-deadline" and system.version == "2.0-regression":
            answer = (
                "A SAR must be filed within 45 calendar days after initial detection. "
                "If no suspect is identified, filing may be delayed up to 60 calendar days. "
                "[aml_transaction_monitoring_policy.md#SAR Filing Timelines]"
            )
            citations = available_required_evidence
        else:
            answer = case.reference_answer or case.expected_behavior
            citations = available_required_evidence
        seed = f"{case.case_key}:{system.version}:{answer}"
        request_id = "local-" + hashlib.sha256(seed.encode()).hexdigest()[:12]
        elapsed = (time.perf_counter() - started) * 1000
        return SystemResponse(
            answer=answer,
            citations=citations,
            retrieved_evidence=retrieved_evidence,
            retrieval_method="bm25",
            generation_mode="deterministic_retrieval_grounded",
            latency_ms=max(round(elapsed, 3), 0.1),
            input_tokens=len(case.input_text.split()) + sum(len(item.text.split()) for item in retrieved),
            output_tokens=len(answer.split()),
            estimated_cost_usd=0.0,
            provider_request_id=request_id,
        )


class GeminiProvider(ModelProvider):
    """Optional adapter boundary; calls remain disabled unless explicitly configured."""

    def generate(self, case: EvaluationCase, system: SystemVersion) -> SystemResponse:
        raise ProviderError(
            "Gemini enterprise adapter is not enabled in local mode; use DeterministicProvider "
            "or configure an approved provider integration"
        )
