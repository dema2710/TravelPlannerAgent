"""Direct, offline tests for the five simulated tools."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from travel_agent.tools.accommodation import search_accommodation
from travel_agent.tools.attractions import search_attractions
from travel_agent.tools.errors import ToolError
from travel_agent.tools.flights import search_flights
from travel_agent.tools.planner import create_daily_itinerary
from travel_agent.tools.weather import get_weather

PARIS_START = date(2027, 5, 10)
PARIS_END = date(2027, 5, 12)


def _planner_attractions(
    destination: str = "Paris",
    interests: list[str] | None = None,
    dietary: list[str] | None = None,
    currency: str = "EUR",
) -> list[dict[str, Any]]:
    data = search_attractions(
        destination,
        interests or ["architecture", "museums", "history"],
        dietary or [],
        currency,
    )
    return data["attractions"]


def test_weather_returns_one_entry_per_day() -> None:
    result = get_weather("Paris", PARIS_START, PARIS_END)
    assert result["simulated"] is True
    assert result["destination"] == "Paris"
    assert [day["date"] for day in result["days"]] == [
        "2027-05-10",
        "2027-05-11",
        "2027-05-12",
    ]
    for day in result["days"]:
        assert 0 <= day["precipitation_probability"] <= 100
        assert day["min_temp_c"] <= day["max_temp_c"]


def test_weather_rejects_invalid_range_and_unknown_city() -> None:
    with pytest.raises(ToolError, match="earlier"):
        get_weather("Paris", PARIS_END, PARIS_START)
    with pytest.raises(ToolError, match="Unsupported destination"):
        get_weather("Atlantis", PARIS_START, PARIS_END)


def test_weather_is_deterministic() -> None:
    first = get_weather("Prague", date(2027, 9, 3), date(2027, 9, 6))
    second = get_weather("Prague", date(2027, 9, 3), date(2027, 9, 6))
    assert first == second


def test_flights_are_sorted_and_include_required_fields() -> None:
    result = search_flights("Paris", PARIS_START, PARIS_END)
    options = result["options"]
    assert result["simulated"] is True
    assert result["departure_city"] == "Prague"
    assert result["origin"] == "Prague (PRG)"
    assert result["destination"] == "Paris (CDG)"
    assert len(options) >= 3
    assert [option["price"] for option in options] == sorted(
        option["price"] for option in options
    )
    first = options[0]
    assert first["origin_city"] == "Prague"
    assert first["origin_airport"] == "PRG"
    assert first["destination_city"] == "Paris"
    assert first["destination_airport"] == "CDG"
    for field in (
        "airline",
        "origin_city",
        "destination_city",
        "departure_date",
        "return_date",
        "outbound_departure_time",
        "return_departure_time",
        "price",
        "currency",
    ):
        assert first[field] is not None


@pytest.mark.parametrize(
    ("departure_city", "origin_airport"),
    [
        ("Prague", "PRG"),
        ("Berlin", "BER"),
        ("Vienna", "VIE"),
        ("London", "LGW"),
    ],
)
def test_flights_support_multiple_departure_cities(
    departure_city: str,
    origin_airport: str,
) -> None:
    result = search_flights(
        "Paris",
        PARIS_START,
        PARIS_END,
        departure_city=departure_city,
    )
    assert result["departure_city"] == departure_city
    assert result["origin"] == f"{departure_city} ({origin_airport})"
    assert result["options"]
    for option in result["options"]:
        assert option["origin_city"] == departure_city
        assert option["origin_airport"] == origin_airport
        assert option["destination_city"] == "Paris"
        assert option["destination_airport"] == "CDG"


def test_flights_resolve_departure_aliases() -> None:
    prague = search_flights(
        "Paris", PARIS_START, PARIS_END, departure_city="praha"
    )
    vienna = search_flights(
        "Paris", PARIS_START, PARIS_END, departure_city="wien"
    )
    assert prague["departure_city"] == "Prague"
    assert vienna["departure_city"] == "Vienna"


def test_flights_reject_unsupported_or_same_city_departure() -> None:
    with pytest.raises(ToolError, match="Unsupported departure city"):
        search_flights(
            "Paris", PARIS_START, PARIS_END, departure_city="Madrid"
        )
    with pytest.raises(ToolError, match="Departure city and destination are both Prague"):
        search_flights(
            "Prague",
            date(2027, 9, 3),
            date(2027, 9, 6),
            departure_city="Prague",
        )


def test_flight_origin_is_reflected_in_price_and_route() -> None:
    prague = search_flights(
        "Paris", PARIS_START, PARIS_END, departure_city="Prague"
    )["options"][0]
    london = search_flights(
        "Paris", PARIS_START, PARIS_END, departure_city="London"
    )["options"][0]
    assert prague["price"] < london["price"]
    assert prague["flight_id"].startswith("FL-PRG-CDG-")
    assert london["flight_id"].startswith("FL-LGW-CDG-")


def test_flight_budget_filter_and_empty_result() -> None:
    all_options = search_flights("Paris", PARIS_START, PARIS_END)["options"]
    cheapest = all_options[0]["price"]
    filtered = search_flights("Paris", PARIS_START, PARIS_END, budget=cheapest)["options"]
    assert filtered
    assert all(option["price"] <= cheapest for option in filtered)

    with pytest.raises(ToolError, match="No simulated flight"):
        search_flights("Paris", PARIS_START, PARIS_END, budget=0.01)


def test_flights_validate_dates_and_support_currency_conversion() -> None:
    with pytest.raises(ToolError, match="return_date"):
        search_flights("Paris", PARIS_END, PARIS_START)

    eur = search_flights("Paris", PARIS_START, PARIS_END, currency="EUR")["options"][0]
    usd = search_flights("Paris", PARIS_START, PARIS_END, currency="USD")["options"][0]
    assert usd["currency"] == "USD"
    assert usd["price"] > eur["price"]


def test_accommodation_totals_and_sorting() -> None:
    result = search_accommodation("Prague", date(2027, 9, 3), date(2027, 9, 6))
    options = result["options"]
    assert result["nights"] == 3
    assert result["simulated"] is True
    assert options == sorted(options, key=lambda option: option["total_price"])
    for option in options:
        assert option["nights"] == 3
        assert option["total_price"] == pytest.approx(
            option["price_per_night"] * 3, abs=0.02
        )
        assert option["check_in"] == "2027-09-03"
        assert option["check_out"] == "2027-09-06"


def test_accommodation_budget_filter_and_empty_result() -> None:
    options = search_accommodation("Prague", date(2027, 9, 3), date(2027, 9, 6))["options"]
    cheapest = options[0]["price_per_night"]
    filtered = search_accommodation(
        "Prague",
        date(2027, 9, 3),
        date(2027, 9, 6),
        budget_per_night=cheapest,
    )["options"]
    assert filtered
    assert all(option["price_per_night"] <= cheapest for option in filtered)

    with pytest.raises(ToolError, match="No simulated accommodation"):
        search_accommodation(
            "Prague",
            date(2027, 9, 3),
            date(2027, 9, 6),
            budget_per_night=0.01,
        )


def test_attractions_are_filtered_by_interest() -> None:
    result = search_attractions("Paris", ["museums"], [], "EUR")
    assert result["simulated"] is True
    assert result["matched_interests"] == ["museums"]
    assert result["attractions"]
    non_food = [item for item in result["attractions"] if item["category"] != "food"]
    assert non_food
    for attraction in non_food:
        assert "museums" in attraction["interests"]


def test_attractions_respect_vegetarian_filter() -> None:
    result = search_attractions(
        "Paris",
        ["architecture", "history"],
        ["vegetarian"],
        "EUR",
    )
    food = [item for item in result["attractions"] if item["category"] == "food"]
    assert food
    assert all("vegetarian" in item["dietary_tags"] for item in food)
    assert "Le Marais Food Walk" not in {item["name"] for item in food}


def test_dietary_need_surfaces_dining_without_food_interest() -> None:
    result = search_attractions("Paris", ["architecture"], ["vegan"], "EUR")
    food = [item for item in result["attractions"] if item["category"] == "food"]
    assert food
    assert all("vegan" in item["dietary_tags"] for item in food)


def test_attractions_handle_empty_and_invalid_searches() -> None:
    with pytest.raises(ToolError, match="no attractions"):
        search_attractions("Rome", ["shopping"], [], "EUR")
    with pytest.raises(ToolError, match="interests are supported"):
        search_attractions("Paris", ["underwater basket weaving"], [], "EUR")
    with pytest.raises(ToolError, match="Unsupported destination"):
        search_attractions("Atlantis", ["history"], [], "EUR")


def test_attractions_report_unapplied_dietary_preferences() -> None:
    result = search_attractions("Paris", ["food"], ["nut allergy"], "EUR")
    assert "nut allergy" in result["unapplied_dietary_preferences"]


def test_planner_respects_pace_and_excludes_food() -> None:
    attractions = _planner_attractions()
    relaxed = create_daily_itinerary(
        "Paris", PARIS_START, PARIS_END, "relaxed", attractions, "EUR"
    )
    intensive = create_daily_itinerary(
        "Paris", PARIS_START, PARIS_END, "intensive", attractions, "EUR"
    )
    relaxed_days = relaxed["itinerary"]
    intensive_days = intensive["itinerary"]
    assert all(len(day["activities"]) <= 2 for day in relaxed_days)
    assert all(len(day["activities"]) <= 4 for day in intensive_days)
    relaxed_count = sum(len(day["activities"]) for day in relaxed_days)
    intensive_count = sum(len(day["activities"]) for day in intensive_days)
    assert relaxed_count <= intensive_count
    food_ids = {
        item["attraction_id"] for item in attractions if item["category"] == "food"
    }
    scheduled_ids = {
        activity["source_attraction_id"]
        for day in intensive_days
        for activity in day["activities"]
    }
    assert scheduled_ids.isdisjoint(food_ids)


def test_planner_respects_opening_hours_and_closed_days() -> None:
    attractions = _planner_attractions()
    by_id = {item["attraction_id"]: item for item in attractions}
    result = create_daily_itinerary(
        "Paris", PARIS_START, PARIS_END, "intensive", attractions, "EUR"
    )
    for day in result["itinerary"]:
        day_date = date.fromisoformat(day["date"])
        for activity in day["activities"]:
            source = by_id[activity["source_attraction_id"]]
            assert day_date.weekday() not in source["closed_weekdays"]
            opening, closing = source["opening_hours"].split("-")
            assert activity["start_time"] >= opening
            assert activity["end_time"] <= closing


def test_planner_daily_and_total_budget_arithmetic() -> None:
    result = create_daily_itinerary(
        "Paris",
        PARIS_START,
        PARIS_END,
        "moderate",
        _planner_attractions(),
        "EUR",
    )
    activity_total = 0.0
    food_total = 0.0
    transport_total = 0.0
    for day in result["itinerary"]:
        activities = sum(item["estimated_cost"] for item in day["activities"])
        expected = activities + day["daily_food_estimate"] + day["local_transport_estimate"]
        assert day["daily_total"] == pytest.approx(expected, abs=0.02)
        activity_total += activities
        food_total += day["daily_food_estimate"]
        transport_total += day["local_transport_estimate"]
    assert result["totals"]["activities"] == pytest.approx(activity_total, abs=0.02)
    assert result["totals"]["food"] == pytest.approx(food_total, abs=0.02)
    assert result["totals"]["local_transportation"] == pytest.approx(
        transport_total, abs=0.02
    )


def test_planner_rejects_food_only_and_bad_currency() -> None:
    food = [
        item
        for item in _planner_attractions(dietary=["vegetarian"])
        if item["category"] == "food"
    ]
    assert food
    with pytest.raises(ToolError, match="No schedulable attractions"):
        create_daily_itinerary("Paris", PARIS_START, PARIS_END, "moderate", food, "EUR")

    attractions = _planner_attractions()
    with pytest.raises(ToolError, match="currency"):
        create_daily_itinerary("Paris", PARIS_START, PARIS_END, "moderate", attractions, "USD")


def test_planner_rejects_invalid_dates_and_empty_attractions() -> None:
    attractions = _planner_attractions()
    with pytest.raises(ToolError, match="after start_date"):
        create_daily_itinerary("Paris", PARIS_END, PARIS_START, "moderate", attractions)
    with pytest.raises(ToolError, match="At least one attraction"):
        create_daily_itinerary("Paris", PARIS_START, PARIS_END, "moderate", [], "EUR")
