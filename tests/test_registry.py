"""Tests for tool registration, schema exposure, and execution boundaries."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from travel_agent.tools import build_default_registry
from travel_agent.tools.registry import ToolDefinition, ToolRegistry


def test_default_registry_exposes_five_tools() -> None:
    registry = build_default_registry()
    assert registry.tool_names == [
        "get_weather",
        "search_flights",
        "search_accommodation",
        "search_attractions",
        "create_daily_itinerary",
    ]
    schemas = registry.openai_tools()
    assert len(schemas) == 5
    for schema in schemas:
        assert schema["type"] == "function"
        assert schema["function"]["name"]
        assert schema["function"]["description"]
        assert schema["function"]["parameters"]["type"] == "object"


def test_registry_executes_valid_tool() -> None:
    registry = build_default_registry()
    result = registry.execute(
        "get_weather",
        {
            "destination": "Paris",
            "start_date": "2027-05-10",
            "end_date": "2027-05-12",
        },
    )
    assert result.ok is True
    assert result.data is not None
    assert len(result.data["days"]) == 3
    assert '"ok": true' in result.content


def test_flight_tool_schema_exposes_departure_city() -> None:
    registry = build_default_registry()
    flight_schema = next(
        schema
        for schema in registry.openai_tools()
        if schema["function"]["name"] == "search_flights"
    )
    departure = flight_schema["function"]["parameters"]["properties"]["departure_city"]
    assert departure["default"] == "Prague"
    assert "departure_city" not in flight_schema["function"]["parameters"].get("required", [])

    result = registry.execute(
        "search_flights",
        {
            "destination": "Paris",
            "departure_city": "Vienna",
            "departure_date": "2027-05-10",
            "return_date": "2027-05-12",
        },
    )
    assert result.ok is True
    assert result.data is not None
    assert result.data["departure_city"] == "Vienna"


def test_registry_rejects_unknown_tool() -> None:
    registry = build_default_registry()
    result = registry.execute("rm_rf", "{}")
    assert result.ok is False
    assert result.error_type == "unknown_tool"
    assert "Unknown tool" in (result.error or "")


def test_registry_rejects_malformed_json() -> None:
    registry = build_default_registry()
    result = registry.execute("get_weather", '{"destination": ')
    assert result.ok is False
    assert result.error_type == "invalid_arguments"
    assert "not valid JSON" in (result.error or "")


def test_registry_rejects_non_object_arguments() -> None:
    registry = build_default_registry()
    result = registry.execute("get_weather", '["Paris"]')
    assert result.ok is False
    assert result.error_type == "invalid_arguments"
    assert "JSON object" in (result.error or "")


def test_registry_rejects_missing_and_extra_arguments() -> None:
    registry = build_default_registry()
    missing = registry.execute("get_weather", {"destination": "Paris"})
    assert missing.ok is False
    assert missing.error_type == "invalid_arguments"

    extra = registry.execute(
        "get_weather",
        {
            "destination": "Paris",
            "start_date": "2027-05-10",
            "end_date": "2027-05-12",
            "unexpected": True,
        },
    )
    assert extra.ok is False
    assert extra.error_type == "invalid_arguments"


def test_registry_returns_tool_errors_without_raising() -> None:
    registry = build_default_registry()
    result = registry.execute(
        "search_flights",
        {
            "destination": "Paris",
            "departure_date": "2027-05-10",
            "return_date": "2027-05-12",
            "budget": 0.01,
        },
    )
    assert result.ok is False
    assert result.error_type == "tool_error"
    assert "No simulated flight" in (result.error or "")


def test_registry_contains_unexpected_exceptions() -> None:
    class DummyInput(BaseModel):
        value: int

    def explode(value: int) -> dict[str, Any]:
        raise RuntimeError(f"boom {value}")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="explode",
            description="Test-only failing tool.",
            input_model=DummyInput,
            handler=explode,
        )
    )
    result = registry.execute("explode", {"value": 3})
    assert result.ok is False
    assert result.error_type == "tool_exception"
    assert "boom 3" in (result.error or "")


def test_registry_rejects_duplicate_registration() -> None:
    registry = build_default_registry()
    definition = registry.get("get_weather")
    assert definition is not None
    try:
        registry.register(definition)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("Duplicate registration should fail.")


def test_blank_arguments_are_treated_as_empty_object() -> None:
    registry = build_default_registry()
    result = registry.execute("get_weather", "   ")
    assert result.ok is False
    assert result.error_type == "invalid_arguments"
