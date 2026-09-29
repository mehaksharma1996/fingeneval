"""Background execution abstraction with eager and local threaded adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

from .config import enterprise_settings
from .db import SessionLocal
from .security import ServiceActor
from .service import EnterpriseService


class JobDispatcher(ABC):
    @abstractmethod
    def submit_run(self, run_id: str, actor: ServiceActor) -> None:
        pass


def _execute(run_id: str, actor: ServiceActor) -> None:
    with SessionLocal() as session:
        EnterpriseService(session).execute_run(run_id, actor)


class EagerJobDispatcher(JobDispatcher):
    def submit_run(self, run_id: str, actor: ServiceActor) -> None:
        _execute(run_id, actor)


class ThreadedJobDispatcher(JobDispatcher):
    """Local-only worker; production deployment replaces this with a durable queue."""

    def __init__(self, workers: int = 2) -> None:
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fingeneval-worker")

    def submit_run(self, run_id: str, actor: ServiceActor) -> None:
        self.pool.submit(_execute, run_id, actor)


dispatcher: JobDispatcher = (
    EagerJobDispatcher() if enterprise_settings.execution_mode == "eager" else ThreadedJobDispatcher()
)
