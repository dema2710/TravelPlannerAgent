"""Offline API tests for the FastAPI website layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from travel_agent.config import Settings
from travel_agent.web.app import create_app


def _payload(
    *,
    mode: str = "offline",
    destination: str = "Paris",
    departure_city: str = "Prague",
) -> dict[str, Any]:
    return {
        "mode": mode,
        "request": {
            "destination": destination,
            "departure_city": departure_city,
            "start_date": "2027-05-10",
            "end_date": "2027-05-12",
            "budget": 800.0,
            "currency": "EUR",
            "pace": "moderate",
            "interests": ["architecture", "museums", "history"],
            "dietary_restrictions": ["vegetarian"],
        },
    }


@pytest.fixture
def web_client(tmp_path: Path) -> tuple[TestClient, Path]:
    trace_dir = tmp_path / "traces"
    app = create_app(Settings(deepseek_api_key=None, trace_dir=trace_dir))
    with TestClient(app) as client:
        yield client, trace_dir


def test_homepage_and_static_assets(web_client: tuple[TestClient, Path]) -> None:
    client, _ = web_client
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "Travel Planner" in page.text
    assert "/static/app.js" in page.text

    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/app.js")
    assert stylesheet.status_code == 200
    assert "text/css" in stylesheet.headers["content-type"]
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]


def test_config_exposes_form_options(web_client: tuple[TestClient, Path]) -> None:
    client, _ = web_client
    response = client.get("/api/config")
    assert response.status_code == 200
    config = response.json()
    assert "Paris" in config["destinations"]
    assert "Prague" in config["departure_cities"]
    assert config["default_departure_city"] == "Prague"
    assert "EUR" in config["currencies"]
    assert config["paces"] == ["relaxed", "moderate", "intensive"]
    assert "architecture" in config["interests"]
    assert "vegetarian" in config["dietary_preferences"]
    assert config["live_api_available"] is False


def test_health_reports_live_availability(web_client: tuple[TestClient, Path]) -> None:
    client, _ = web_client
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "live_api_available": False}


def test_offline_itinerary_is_generated_and_traced(
    web_client: tuple[TestClient, Path],
) -> None:
    client, trace_dir = web_client
    response = client.post("/api/itineraries", json=_payload())
    assert response.status_code == 200

    data = response.json()
    assert data["mode"] == "offline"
    assert data["provider"] == "offline_scripted"
    assert data["plan"]["request"]["destination"] == "Paris"
    assert data["plan"]["request"]["departure_city"] == "Prague"
    assert data["plan"]["selected_flight"]["origin_city"] == "Prague"
    assert len(data["plan"]["daily_itinerary"]) == 3
    assert data["plan"]["budget_breakdown"]["budget_respected"] is True

    trace_path = Path(data["trace_file"])
    assert trace_path.is_relative_to(trace_dir)
    assert trace_path.exists()
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["event"] == "run_started"
    assert events[0]["mode"] == "web_offline_simulated"
    assert events[-1]["event"] == "run_finished"
    assert events[-1]["status"] == "success"
    assert any(event["event"] == "final_output" for event in events)


def test_invalid_travel_request_returns_structured_422(
    web_client: tuple[TestClient, Path],
) -> None:
    client, _ = web_client
    response = client.post(
        "/api/itineraries",
        json=_payload(destination="Prague", departure_city="Prague"),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "Departure city must differ" in " ".join(body["error"]["details"])


def test_live_mode_without_key_returns_structured_503(
    web_client: tuple[TestClient, Path],
) -> None:
    client, _ = web_client
    response = client.post("/api/itineraries", json=_payload(mode="live"))
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "live_mode_unavailable"
    assert "DEEPSEEK_API_KEY" in body["error"]["message"]


def test_config_reports_live_mode_when_key_is_present(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            deepseek_api_key="test-key-not-real",
            trace_dir=tmp_path / "traces",
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["live_api_available"] is True
