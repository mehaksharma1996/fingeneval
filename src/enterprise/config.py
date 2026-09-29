"""Environment configuration for the enterprise service."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class EnterpriseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINGENEVAL_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'fingeneval.db').as_posix()}"
    execution_mode: str = "eager"
    local_auth_enabled: bool = True
    max_upload_bytes: int = 10 * 1024 * 1024
    report_dir: Path = PROJECT_ROOT / "reports" / "generated"
    log_level: str = "INFO"


enterprise_settings = EnterpriseSettings()
