"""Swappable report/object storage boundary."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from .config import enterprise_settings


class ObjectStorage(ABC):
    @abstractmethod
    def put_text(self, object_key: str, content: str) -> tuple[str, str]:
        """Return the stored object key and SHA-256 digest."""


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or enterprise_settings.report_dir).resolve()

    def put_text(self, object_key: str, content: str) -> tuple[str, str]:
        target = (self.root / object_key).resolve()
        if self.root not in target.parents:
            raise ValueError("object key escapes configured storage root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return object_key, hashlib.sha256(content.encode()).hexdigest()


class S3ObjectStorage(ObjectStorage):
    """Production adapter contract; deployment must provide an approved SDK client."""

    def put_text(self, object_key: str, content: str) -> tuple[str, str]:
        raise NotImplementedError(
            "S3 storage is a documented production adapter and is not configured locally"
        )
