"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when configuration values are invalid."""


def _read_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw_value!r}.") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}, got {value}.")
    return value


def _read_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw_value!r}.") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}, got {value}.")
    return value


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean value, got {raw_value!r}.")


@dataclass(frozen=True)
class Settings:
    """Runtime settings. The API key is excluded from the generated repr."""

    deepseek_api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    max_iterations: int = 10
    temperature: float = 0.2
    max_tokens: int = 6000
    request_timeout_seconds: float = 60.0
    max_retries: int = 2
    disable_thinking: bool = True
    trace_dir: Path = Path("traces")

    @classmethod
    def load(cls, env_file: str | Path = ".env") -> "Settings":
        """Load settings from a .env file (when present) and the environment."""
        path = Path(env_file)
        if path.exists():
            load_dotenv(dotenv_path=path, override=False)

        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip() or None
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip()
        if not base_url.startswith(("https://", "http://")):
            raise ConfigError("DEEPSEEK_BASE_URL must start with https:// or http://.")
        if not model:
            raise ConfigError("DEEPSEEK_MODEL cannot be empty.")

        return cls(
            deepseek_api_key=api_key,
            base_url=base_url.rstrip("/"),
            model=model,
            max_iterations=_read_int("AGENT_MAX_ITERATIONS", 10, 1, 50),
            temperature=_read_float("DEEPSEEK_TEMPERATURE", 0.2, 0.0, 2.0),
            max_tokens=_read_int("DEEPSEEK_MAX_TOKENS", 6000, 256, 32768),
            request_timeout_seconds=_read_float("DEEPSEEK_TIMEOUT_SECONDS", 60.0, 5.0, 600.0),
            max_retries=_read_int("DEEPSEEK_MAX_RETRIES", 2, 0, 10),
            disable_thinking=_read_bool("DEEPSEEK_DISABLE_THINKING", True),
            trace_dir=Path(os.getenv("TRACE_DIR", "traces")),
        )
