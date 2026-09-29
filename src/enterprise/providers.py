"""Provider-neutral response interface with a deterministic credential-free adapter."""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

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
    """Synthetic adapter used by local demos and tests.

    Candidate version ``2.0-regression`` intentionally changes the mandatory SAR
    deadline to 45 days. Version ``2.0-remediated`` returns the approved answer.
    """

    fail_case_ids: frozenset[str] = frozenset()

    def generate(self, case: EvaluationCase, system: SystemVersion) -> SystemResponse:
        if case.case_key in self.fail_case_ids:
            raise ProviderError(f"simulated provider timeout for {case.case_key}")
        started = time.perf_counter()
        if case.abstention_expected:
            answer = "I cannot determine this from the approved documents or perform that action."
            citations: list[str] = []
        elif case.case_key == "aml-sar-deadline" and system.version == "2.0-regression":
            answer = (
                "A SAR must be filed within 45 calendar days after initial detection. "
                "If no suspect is identified, filing may be delayed up to 60 calendar days. "
                "[aml_transaction_monitoring_policy.md#SAR Filing Timelines]"
            )
            citations = list(case.required_evidence)
        else:
            answer = case.reference_answer or case.expected_behavior
            citations = list(case.required_evidence)
        seed = f"{case.case_key}:{system.version}:{answer}"
        request_id = "local-" + hashlib.sha256(seed.encode()).hexdigest()[:12]
        elapsed = (time.perf_counter() - started) * 1000
        return SystemResponse(
            answer=answer,
            citations=citations,
            latency_ms=max(round(elapsed, 3), 0.1),
            input_tokens=40 + len(case.expected_behavior.split()),
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
