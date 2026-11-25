"""Tests for JSON request loading and departure-city compatibility."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from travel_agent.main import load_request_file


def _write_request(tmp_path: Path, **overrides: Any) -> Path:
    payload: dict[str, Any] = {
        "destination": "Paris",
        "start_date": "2027-05-10",
        "end_date": "2027-05-12",
        "budget": 800.0,
        "currency": "EUR",
        "pace": "moderate",
        "interests": ["architecture", "museums", "history"],
        "dietary_restrictions": ["vegetarian"],
    }
    payload.update(overrides)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_request_file_without_departure_city_uses_prague(tmp_path: Path) -> None:
    request = load_request_file(_write_request(tmp_path))
    assert request.departure_city == "Prague"


def test_request_file_accepts_explicit_departure_city(tmp_path: Path) -> None:
    request = load_request_file(
        _write_request(tmp_path, departure_city="berlin")
    )
    assert request.departure_city == "Berlin"


def test_request_file_canonicalizes_destination_and_departure(tmp_path: Path) -> None:
    request = load_request_file(
        _write_request(tmp_path, destination="Praha", departure_city="Wien")
    )
    assert request.destination == "Prague"
    assert request.departure_city == "Vienna"


def test_request_file_rejects_same_departure_and_destination(tmp_path: Path) -> None:
    path = _write_request(tmp_path, destination="Prague")
    with pytest.raises(ValueError, match="Departure city must differ"):
        load_request_file(path)


def test_request_file_rejects_unsupported_departure_city(tmp_path: Path) -> None:
    path = _write_request(tmp_path, departure_city="Madrid")
    with pytest.raises(ValueError, match="Unsupported departure city"):
        load_request_file(path)
