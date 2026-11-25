"""JSONL execution trace writer.

Each run writes one JSON object per line. Messages contain no API key or HTTP
headers. The logger records the exact messages sent to and received from the
LLM, every tool call/result, validation retries, and the final plan.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return str(value)


class TraceLogger:
    """Append-only JSONL trace for one agent run."""

    def __init__(self, path: str | Path, run_id: str, mode: str = "live") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.mode = mode
        self._file = self.path.open("w", encoding="utf-8")

    def log(self, event: str, **fields: Any) -> None:
        """Write one JSONL event. Never include credentials in trace fields."""
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
        }
        record.update(fields)
        self._file.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")
        self._file.flush()

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "TraceLogger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
