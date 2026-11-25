"""Validation tests for structured travel-plan models."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from pydantic import ValidationError

from travel_agent.schemas import (
    AccommodationOption,
    BudgetBreakdown,
    DailyItinerary,
    TravelPlan,
    TravelRequest,
    WeatherInfo,
)


def _request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "destination": "Paris",
        "start_date": "2027-05-10",
        "end_date": "2027-05-12",
        "budget": 800.0,
        "currency": "eur",
        "pace": "Moderate",
        "interests": ["Architecture", "museums", "museums", "history"],
        "dietary_restrictions": ["Vegetarian", "vegetarian"],
    }
    payload.update(overrides)
    return payload


def test_request_normalizes_values_and_computes_duration() -> None:
    request = TravelRequest.model_validate(_request())
    assert request.currency == "EUR"
    assert request.pace == "moderate"
    assert request.interests == ["architecture", "museums", "history"]
    assert request.dietary_restrictions == ["vegetarian"]
    assert request.departure_city == "Prague"
    assert request.nights == 2
    assert request.days == 3
    assert len(request.date_range()) == 3


def test_request_normalizes_explicit_departure_city() -> None:
    request = TravelRequest.model_validate(_request(departure_city="berlin"))
    assert request.departure_city == "Berlin"

    alias_request = TravelRequest.model_validate(_request(departure_city="wien"))
    assert alias_request.departure_city == "Vienna"

    null_departure = TravelRequest.model_validate(_request(departure_city=None))
    assert null_departure.departure_city == "Prague"


def test_request_rejects_unsupported_departure_city() -> None:
    with pytest.raises(ValidationError, match="Unsupported departure city"):
        TravelRequest.model_validate(_request(departure_city="Madrid"))


def test_request_rejects_same_departure_and_destination() -> None:
    with pytest.raises(ValidationError, match="Departure city must differ"):
        TravelRequest.model_validate(_request(destination="Prague"))

    with pytest.raises(ValidationError, match="Departure city must differ"):
        TravelRequest.model_validate(
            _request(destination="Praha", departure_city="Prague")
        )


def test_request_allows_prague_with_another_origin() -> None:
    request = TravelRequest.model_validate(
        _request(destination="Prague", departure_city="Berlin")
    )
    assert request.destination == "Prague"
    assert request.departure_city == "Berlin"


@pytest.mark.parametrize(
    "overrides",
    [
        {"end_date": "2027-05-10"},
        {"end_date": "2027-05-09"},
        {"budget": 0},
        {"budget": -5},
        {"budget": float("inf")},
        {"currency": "XYZ"},
        {"interests": []},
        {"pace": "very fast"},
        {"departure_city": "Madrid"},
    ],
)
def test_invalid_request_fields_raise(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TravelRequest.model_validate(_request(**overrides))


def test_request_limits_trip_length() -> None:
    with pytest.raises(ValidationError):
        TravelRequest.model_validate(_request(end_date="2027-05-30"))


def test_weather_rejects_reversed_temperatures() -> None:
    with pytest.raises(ValidationError):
        WeatherInfo(
            date=date(2027, 5, 10),
            condition="Sunny",
            min_temp_c=20,
            max_temp_c=10,
            precipitation_probability=20,
        )


def test_accommodation_total_is_checked() -> None:
    with pytest.raises(ValidationError):
        AccommodationOption(
            hotel_id="H1",
            name="Hotel",
            category="budget",
            location="Paris",
            rating=4.0,
            check_in=date(2027, 5, 10),
            check_out=date(2027, 5, 12),
            price_per_night=100.0,
            nights=2,
            total_price=250.0,
            currency="EUR",
        )


def test_daily_total_is_checked(paris_plan: TravelPlan) -> None:
    payload = paris_plan.daily_itinerary[0].model_dump(mode="json")
    payload["daily_total"] = 1.0
    with pytest.raises(ValidationError):
        DailyItinerary.model_validate(payload)


def test_budget_math_is_checked() -> None:
    with pytest.raises(ValidationError):
        BudgetBreakdown(
            currency="EUR",
            flights=100,
            accommodation=100,
            food=100,
            activities=100,
            local_transportation=100,
            total_estimated_cost=400,
            budget=500,
            remaining_budget=100,
            budget_respected=True,
        )


def test_budget_respected_cannot_be_claimed_when_over_budget() -> None:
    with pytest.raises(ValidationError):
        BudgetBreakdown(
            currency="EUR",
            flights=100,
            accommodation=100,
            food=100,
            activities=100,
            local_transportation=100,
            total_estimated_cost=500,
            budget=450,
            remaining_budget=-50,
            budget_respected=True,
        )


def test_truthful_over_budget_plan_is_schema_valid(paris_plan: TravelPlan) -> None:
    payload = deepcopy(paris_plan.model_dump(mode="json"))
    total = payload["budget_breakdown"]["total_estimated_cost"]
    new_budget = round(total - 100, 2)
    payload["request"]["budget"] = new_budget
    payload["budget_breakdown"]["budget"] = new_budget
    payload["budget_breakdown"]["remaining_budget"] = round(new_budget - total, 2)
    payload["budget_breakdown"]["budget_respected"] = False

    plan = TravelPlan.model_validate(payload)
    assert plan.budget_breakdown.budget_respected is False
    assert plan.budget_breakdown.remaining_budget < 0


def test_plan_rejects_missing_itinerary_day(paris_plan: TravelPlan) -> None:
    payload = deepcopy(paris_plan.model_dump(mode="json"))
    payload["daily_itinerary"].pop()
    with pytest.raises(ValidationError, match="exactly 3 days"):
        TravelPlan.model_validate(payload)


def test_plan_rejects_weather_date_mismatch(paris_plan: TravelPlan) -> None:
    payload = deepcopy(paris_plan.model_dump(mode="json"))
    payload["weather"][0]["date"] = "2027-05-09"
    with pytest.raises(ValidationError, match="Weather entries"):
        TravelPlan.model_validate(payload)


def test_plan_rejects_flight_date_mismatch(paris_plan: TravelPlan) -> None:
    payload = deepcopy(paris_plan.model_dump(mode="json"))
    payload["selected_flight"]["departure_date"] = "2027-05-09"
    with pytest.raises(ValidationError, match="departure_date"):
        TravelPlan.model_validate(payload)


def test_plan_rejects_flight_from_wrong_departure_city(paris_plan: TravelPlan) -> None:
    payload = deepcopy(paris_plan.model_dump(mode="json"))
    payload["selected_flight"]["origin_city"] = "Vienna"
    payload["selected_flight"]["origin_airport"] = "VIE"
    with pytest.raises(ValidationError, match="origin_city"):
        TravelPlan.model_validate(payload)


def test_plan_requires_simulated_disclaimer(paris_plan: TravelPlan) -> None:
    payload = deepcopy(paris_plan.model_dump(mode="json"))
    payload["data_disclaimer"] = "This is real-time verified information from providers."
    with pytest.raises(ValidationError, match="simulated"):
        TravelPlan.model_validate(payload)


def test_plan_rejects_extra_fields(paris_plan: TravelPlan) -> None:
    payload = deepcopy(paris_plan.model_dump(mode="json"))
    payload["unexpected"] = "value"
    with pytest.raises(ValidationError):
        TravelPlan.model_validate(payload)


def test_plan_round_trips_through_json(paris_plan: TravelPlan) -> None:
    restored = TravelPlan.model_validate_json(paris_plan.model_dump_json())
    assert restored == paris_plan
