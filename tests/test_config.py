"""Tests for environment-based configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from travel_agent.config import ConfigError, Settings


def _clear_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "AGENT_MAX_ITERATIONS",
        "DEEPSEEK_TEMPERATURE",
        "DEEPSEEK_MAX_TOKENS",
        "DEEPSEEK_TIMEOUT_SECONDS",
        "DEEPSEEK_MAX_RETRIES",
        "DEEPSEEK_DISABLE_THINKING",
        "TRACE_DIR",
    ):
        monkeypatch.delenv(name, raising=False)


def test_settings_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_environment(monkeypatch)
    settings = Settings.load(tmp_path / "missing.env")
    assert settings.deepseek_api_key is None
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.model == "deepseek-flash"
    assert settings.max_iterations == 10
    assert settings.trace_dir == Path("traces")
    assert "secret" not in repr(settings).lower()


def test_settings_read_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_environment(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "5")
    settings = Settings.load(tmp_path / "missing.env")
    assert settings.deepseek_api_key == "test-key-not-real"
    assert settings.model == "deepseek-v4-pro"
    assert settings.max_iterations == 5
    assert "test-key-not-real" not in repr(settings)


def test_settings_reject_invalid_iteration_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_environment(monkeypatch)
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "0")
    with pytest.raises(ConfigError, match="AGENT_MAX_ITERATIONS"):
        Settings.load(tmp_path / "missing.env")
