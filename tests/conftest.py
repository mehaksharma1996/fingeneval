"""Shared fixtures: tests never call the real Gemini API, even when .env has a key."""

import pytest

from src import llm


@pytest.fixture(autouse=True)
def offline_llm(monkeypatch):
    """Blank the API key and quota state; tests opt in to a fake key via `api_key`."""
    original = llm.settings.gemini_api_key
    object.__setattr__(llm.settings, "gemini_api_key", None)
    llm.reset_daily_quota_flag()
    monkeypatch.setattr(llm, "call_gemini", lambda prompt: pytest.fail("real Gemini call attempted in tests"))
    yield
    object.__setattr__(llm.settings, "gemini_api_key", original)
    llm.reset_daily_quota_flag()
