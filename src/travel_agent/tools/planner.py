"""Simulated day planner tool.

The planner only schedules attractions supplied by the caller. It does not
invent attractions or prices. It does add deterministic daily estimates for
meals and local transport, and it clearly labels those estimates as simulated.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from travel_agent.mock_data import resolve_city, supported_destination_names
from travel_agent.schemas import (
    MAX_TRIP_DAYS,
    Attraction,
    DailyActivity,
    DailyItinerary,
    Pace,
)
from travel_agent.tools.errors import ToolError
from travel_agent.utils.money import convert_from_eur, normalize_currency, round_money

TOOL_NAME = "create_daily_itinerary"
TOOL_DESCRIPTION = (
    "Assemble a day-by-day SIMULATED itinerary from attractions returned by "
    "search_attractions. The tool respects pace, opening days, opening hours, "
    "duration, and adds simulated daily food and local-transport estimates. "
    "Restaurants (category 'food') are excluded from paid activities to avoid double counting."
)

PACE_ACTIVITY_LIMITS: dict[str, int] = {
    "relaxed": 2,
    "moderate": 3,
    "intensive": 4,
}
PACE_TRANSPORT_MULTIPLIERS: dict[str, float] = {
    "relaxed": 0.8,
    "moderate": 1.0,
    "intensive": 1.3,
}
DAY_START_MINUTES = 10 * 60
LATEST_END_MINUTES = 22 * 60
TRANSFER_MINUTES = 30


class ItineraryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(min_length=1)
    start_date: date
    end_date: date
    pace: Pace
    attractions: list[Attraction] = Field(min_length=1)
    currency: str = "EUR"

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("pace", mode="before")
    @classmethod
    def normalize_pace(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_query(self) -> "ItineraryQuery":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date.")
        if (self.end_date - self.start_date).days > MAX_TRIP_DAYS:
            raise ValueError(f"Trips are limited to {MAX_TRIP_DAYS} days.")
        mismatched = [
            attraction.name
            for attraction in self.attractions
            if attraction.currency != self.currency
        ]
        if mismatched:
            raise ValueError(
                "All attraction prices must use the requested currency. "
                f"Mismatched attractions: {', '.join(mismatched[:3])}."
            )
        return self


def _minutes_to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _opening_window(attraction: Attraction) -> tuple[int, int]:
    if not attraction.opening_hours:
        return 0, 24 * 60
    start_text, end_text = attraction.opening_hours.split("-", maxsplit=1)
    start_hour, start_minute = (int(part) for part in start_text.split(":"))
    end_hour, end_minute = (int(part) for part in end_text.split(":"))
    return start_hour * 60 + start_minute, end_hour * 60 + end_minute


def _day_theme(activities: list[DailyActivity], destination: str) -> str:
    if not activities:
        return f"Free time and rest in {destination}"
    categories: list[str] = []
    for activity in activities:
        label = activity.category.replace("_", " ").title()
        if label not in categories:
            categories.append(label)
    return f"{' & '.join(categories[:2])} in {destination}"


def create_daily_itinerary(
    destination: str,
    start_date: date,
    end_date: date,
    pace: Pace,
    attractions: list[Attraction | dict[str, Any]],
    currency: str = "EUR",
) -> dict[str, Any]:
    """Schedule supplied attractions and return a validated simulated itinerary."""
    if end_date <= start_date:
        raise ToolError("end_date must be after start_date.")
    if (end_date - start_date).days > MAX_TRIP_DAYS:
        raise ToolError(f"Trips are limited to {MAX_TRIP_DAYS} days.")
    if not attractions:
        raise ToolError("At least one attraction is required to build an itinerary.")

    city = resolve_city(destination)
    if city is None:
        supported = ", ".join(supported_destination_names())
        raise ToolError(
            f"Unsupported destination for the simulated day planner: '{destination}'. "
            f"Supported destinations: {supported}."
        )

    validated_attractions = [
        attraction
        if isinstance(attraction, Attraction)
        else Attraction.model_validate(attraction)
        for attraction in attractions
    ]
    mismatched_currency = [
        attraction.name
        for attraction in validated_attractions
        if attraction.currency != currency
    ]
    if mismatched_currency:
        raise ToolError(
            "All attraction prices must use the requested currency. Mismatched: "
            + ", ".join(mismatched_currency[:3])
            + "."
        )
    schedulable = [
        attraction for attraction in validated_attractions if attraction.category != "food"
    ]
    if not schedulable:
        raise ToolError(
            "No schedulable attractions were provided. Restaurants and food venues are "
            "dining suggestions only; pass non-food attractions from search_attractions."
        )

    activity_limit = PACE_ACTIVITY_LIMITS[pace]
    transport_multiplier = PACE_TRANSPORT_MULTIPLIERS[pace]
    total_days = (end_date - start_date).days + 1
    remaining = list(schedulable)
    itinerary: list[DailyItinerary] = []

    for day_index in range(total_days):
        current_date = date.fromordinal(start_date.toordinal() + day_index)
        scheduled: list[DailyActivity] = []
        current_minutes = DAY_START_MINUTES

        for attraction in list(remaining):
            if len(scheduled) >= activity_limit:
                break
            if current_date.weekday() in attraction.closed_weekdays:
                continue

            opening, closing = _opening_window(attraction)
            duration = max(15, int(round(attraction.duration_hours * 60)))
            start_minutes = max(current_minutes, opening)
            end_minutes = start_minutes + duration
            if end_minutes > closing or end_minutes > LATEST_END_MINUTES:
                continue

            scheduled.append(
                DailyActivity(
                    source_attraction_id=attraction.attraction_id,
                    name=attraction.name,
                    category=attraction.category,
                    description=attraction.description,
                    start_time=_minutes_to_time(start_minutes),
                    end_time=_minutes_to_time(end_minutes),
                    estimated_cost=attraction.price,
                    currency=currency,
                    location=attraction.location,
                )
            )
            remaining.remove(attraction)
            current_minutes = end_minutes + TRANSFER_MINUTES

        food_estimate = convert_from_eur(city.food_per_day_eur, currency)
        transport_estimate = convert_from_eur(
            city.local_transport_per_day_eur * transport_multiplier,
            currency,
        )
        activity_total = round_money(sum(activity.estimated_cost for activity in scheduled))
        daily_total = round_money(activity_total + food_estimate + transport_estimate)

        itinerary.append(
            DailyItinerary(
                day_number=day_index + 1,
                date=current_date,
                theme=_day_theme(scheduled, city.name),
                activities=scheduled,
                daily_food_estimate=food_estimate,
                local_transport_estimate=transport_estimate,
                daily_total=daily_total,
                currency=currency,
            )
        )

    if not any(day.activities for day in itinerary):
        raise ToolError(
            "None of the supplied attractions could be scheduled within their opening hours, "
            "closed days, and the requested pace. Try broader or different attractions."
        )

    activity_total = round_money(
        sum(activity.estimated_cost for day in itinerary for activity in day.activities)
    )
    food_total = round_money(sum(day.daily_food_estimate for day in itinerary))
    transport_total = round_money(sum(day.local_transport_estimate for day in itinerary))

    return {
        "simulated": True,
        "destination": city.name,
        "pace": pace,
        "currency": currency,
        "itinerary": [day.model_dump(mode="json") for day in itinerary],
        "totals": {
            "activities": activity_total,
            "food": food_total,
            "local_transportation": transport_total,
        },
        "unscheduled_attractions": [attraction.name for attraction in remaining],
        "note": (
            "SIMULATED schedule. Meal and local-transport amounts are deterministic estimates; "
            "attraction prices come from the simulated catalogue. Food venues are not counted "
            "as paid activities."
        ),
    }
