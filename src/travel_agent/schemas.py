"""Pydantic models used for inputs, tool data, and the final structured plan.

The final ``TravelPlan`` model deliberately checks cross-field consistency. An
LLM response that invents a total, a remaining budget, or a misleading
"budget respected" flag is rejected rather than displayed.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from travel_agent.mock_data import (
    DEFAULT_DEPARTURE_CITY,
    resolve_city,
    resolve_departure_city,
    supported_departure_names,
)
from travel_agent.utils.money import normalize_currency

Pace = Literal["relaxed", "moderate", "intensive"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]

MAX_TRIP_DAYS = 14
MONEY_TOLERANCE = 0.02


def _approx_equal(left: float, right: float, tolerance: float = MONEY_TOLERANCE) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def _time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


class DomainModel(BaseModel):
    """Base model: reject unexpected fields so mistakes are visible."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TravelRequest(DomainModel):
    """A validated travel request supplied by the user."""

    destination: str = Field(min_length=1, max_length=80)
    departure_city: str = Field(
        default=DEFAULT_DEPARTURE_CITY,
        min_length=1,
        max_length=80,
    )
    start_date: date
    end_date: date
    budget: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    pace: Pace
    interests: list[str] = Field(min_length=1)
    dietary_restrictions: list[str] = Field(default_factory=list)

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Destination cannot be empty.")
        return cleaned

    @field_validator("departure_city", mode="before")
    @classmethod
    def apply_default_departure_city(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return DEFAULT_DEPARTURE_CITY
        return value

    @field_validator("departure_city")
    @classmethod
    def validate_departure_city(cls, value: str) -> str:
        resolved = resolve_departure_city(value)
        if resolved is None:
            supported = ", ".join(supported_departure_names())
            raise ValueError(
                f"Unsupported departure city '{value}'. Supported departure cities: {supported}."
            )
        return resolved.name

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Budget must be a finite number.")
        return round(float(value), 2)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("pace", mode="before")
    @classmethod
    def normalize_pace(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("interests", "dietary_restrictions")
    @classmethod
    def normalize_text_list(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            cleaned = " ".join(value.strip().lower().split())
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> "TravelRequest":
        if self.end_date <= self.start_date:
            raise ValueError("End date must be after start date (at least one overnight stay).")
        nights = (self.end_date - self.start_date).days
        if nights > MAX_TRIP_DAYS - 1:
            raise ValueError(f"Trips are limited to {MAX_TRIP_DAYS} days.")
        return self

    @model_validator(mode="after")
    def validate_route(self) -> "TravelRequest":
        destination = resolve_city(self.destination)
        departure = resolve_departure_city(self.departure_city)
        if destination is not None and departure is not None:
            if destination.key == departure.key:
                raise ValueError(
                    "Departure city must differ from destination. Provide another "
                    "departure_city, or choose a different destination."
                )
        return self

    @property
    def nights(self) -> int:
        return (self.end_date - self.start_date).days

    @property
    def days(self) -> int:
        return self.nights + 1

    def date_range(self) -> list[date]:
        return [self.start_date + timedelta(days=offset) for offset in range(self.days)]


class WeatherInfo(DomainModel):
    """Simulated weather for one day of the trip."""

    date: date
    condition: str = Field(min_length=1)
    min_temp_c: float
    max_temp_c: float
    precipitation_probability: int = Field(ge=0, le=100)
    simulated: Literal[True] = True

    @model_validator(mode="after")
    def validate_temperatures(self) -> "WeatherInfo":
        if self.min_temp_c > self.max_temp_c:
            raise ValueError("Minimum temperature cannot exceed maximum temperature.")
        return self


class FlightOption(DomainModel):
    """A simulated round-trip flight option for one traveller."""

    flight_id: str
    airline: str
    origin_city: str
    origin_airport: str
    destination_city: str
    destination_airport: str
    departure_date: date
    return_date: date
    outbound_departure_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    outbound_arrival_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    return_departure_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    return_arrival_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    stops: int = Field(ge=0, le=2)
    price: float = Field(ge=0)
    currency: str
    simulated: Literal[True] = True

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)


class AccommodationOption(DomainModel):
    """A simulated accommodation option."""

    hotel_id: str
    name: str
    category: str
    location: str
    rating: float = Field(ge=0, le=5)
    check_in: date
    check_out: date
    price_per_night: float = Field(ge=0)
    nights: int = Field(ge=1)
    total_price: float = Field(ge=0)
    currency: str
    simulated: Literal[True] = True

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @model_validator(mode="after")
    def validate_total(self) -> "AccommodationOption":
        if self.check_out <= self.check_in:
            raise ValueError("Accommodation check_out must be after check_in.")
        if (self.check_out - self.check_in).days != self.nights:
            raise ValueError("Accommodation nights must match the check-in/check-out dates.")
        expected = self.price_per_night * self.nights
        if not _approx_equal(expected, self.total_price):
            raise ValueError(
                "Accommodation total_price must equal price_per_night multiplied by nights."
            )
        return self


class Attraction(DomainModel):
    """A simulated attraction, activity, or dining option."""

    attraction_id: str
    name: str
    category: str
    description: str
    duration_hours: float = Field(gt=0, le=12)
    price: float = Field(ge=0)
    currency: str
    opening_hours: str | None = None
    closed_weekdays: list[int] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    dietary_tags: list[str] = Field(default_factory=list)
    meal_type: MealType | None = None
    location: str | None = None
    simulated: Literal[True] = True

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("closed_weekdays")
    @classmethod
    def validate_closed_weekdays(cls, values: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in values):
            raise ValueError("closed_weekdays values must be between 0 (Monday) and 6 (Sunday).")
        return sorted(set(values))

    @field_validator("opening_hours")
    @classmethod
    def validate_opening_hours(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            start_text, end_text = value.split("-", maxsplit=1)
            start, end = _time_to_minutes(start_text.strip()), _time_to_minutes(end_text.strip())
        except (ValueError, AttributeError) as exc:
            raise ValueError("opening_hours must use the 'HH:MM-HH:MM' format.") from exc
        if end <= start:
            raise ValueError("opening_hours end time must be after start time.")
        return f"{start_text.strip()}-{end_text.strip()}"


class DailyActivity(DomainModel):
    """A scheduled activity inside one day's itinerary."""

    source_attraction_id: str
    name: str
    category: str
    description: str
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    estimated_cost: float = Field(ge=0)
    currency: str
    location: str | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "DailyActivity":
        if _time_to_minutes(self.end_time) <= _time_to_minutes(self.start_time):
            raise ValueError("Activity end_time must be after start_time.")
        return self


class DailyItinerary(DomainModel):
    """One day of the trip, including simulated daily expense estimates."""

    day_number: int = Field(ge=1)
    date: date
    theme: str
    activities: list[DailyActivity]
    daily_food_estimate: float = Field(ge=0)
    local_transport_estimate: float = Field(ge=0)
    daily_total: float = Field(ge=0)
    currency: str

    @model_validator(mode="after")
    def validate_daily_total(self) -> "DailyItinerary":
        if any(activity.currency != self.currency for activity in self.activities):
            raise ValueError("Every activity must use the day's requested currency.")
        activity_total = sum(activity.estimated_cost for activity in self.activities)
        expected = activity_total + self.daily_food_estimate + self.local_transport_estimate
        if not _approx_equal(expected, self.daily_total):
            raise ValueError(
                "daily_total must equal activity costs plus food and local transport estimates."
            )
        return self


class BudgetBreakdown(DomainModel):
    """Calculated trip budget. Cross-field values must agree."""

    currency: str
    flights: float = Field(ge=0)
    accommodation: float = Field(ge=0)
    food: float = Field(ge=0)
    activities: float = Field(ge=0)
    local_transportation: float = Field(ge=0)
    total_estimated_cost: float = Field(ge=0)
    budget: float = Field(gt=0)
    remaining_budget: float
    budget_respected: bool

    @model_validator(mode="after")
    def validate_budget_math(self) -> "BudgetBreakdown":
        expected_total = (
            self.flights
            + self.accommodation
            + self.food
            + self.activities
            + self.local_transportation
        )
        if not _approx_equal(expected_total, self.total_estimated_cost):
            raise ValueError(
                "total_estimated_cost must equal the sum of flights, accommodation, "
                "food, activities, and local transportation."
            )
        expected_remaining = self.budget - self.total_estimated_cost
        if not _approx_equal(expected_remaining, self.remaining_budget):
            raise ValueError("remaining_budget must equal budget minus total_estimated_cost.")
        expected_respected = self.total_estimated_cost <= self.budget
        if self.budget_respected != expected_respected:
            raise ValueError("budget_respected must reflect the calculated total cost.")
        return self


class TravelPlan(DomainModel):
    """The final, validated travel plan returned by the agent."""

    request: TravelRequest
    summary: str = Field(min_length=20)
    weather: list[WeatherInfo] = Field(min_length=1)
    selected_flight: FlightOption
    selected_accommodation: AccommodationOption
    daily_itinerary: list[DailyItinerary] = Field(min_length=1)
    budget_breakdown: BudgetBreakdown
    recommendations: list[str] = Field(min_length=1)
    practical_notes: list[str] = Field(min_length=1)
    data_disclaimer: str = Field(min_length=20)

    @model_validator(mode="after")
    def validate_plan_consistency(self) -> "TravelPlan":
        request = self.request
        budget = self.budget_breakdown
        flight = self.selected_flight
        hotel = self.selected_accommodation

        if len(self.daily_itinerary) != request.days:
            raise ValueError(
                f"daily_itinerary must contain exactly {request.days} days for the requested trip."
            )
        expected_dates = request.date_range()
        for day_number, (day, expected_date) in enumerate(
            zip(self.daily_itinerary, expected_dates), start=1
        ):
            if day.day_number != day_number:
                raise ValueError("Itinerary day numbers must start at 1 and be sequential.")
            if day.date != expected_date:
                raise ValueError("Itinerary dates must match the requested travel dates in order.")
            if day.currency != request.currency:
                raise ValueError("Every itinerary day must use the requested currency.")

        weather_dates = [item.date for item in self.weather]
        if weather_dates != expected_dates:
            raise ValueError("Weather entries must match every trip date in order.")

        if flight.departure_date != request.start_date:
            raise ValueError("Selected flight departure_date must match the trip start date.")
        if flight.return_date != request.end_date:
            raise ValueError("Selected flight return_date must match the trip end date.")
        if flight.currency != request.currency:
            raise ValueError("Selected flight currency must match the requested currency.")
        if flight.origin_city.casefold() != request.departure_city.casefold():
            raise ValueError(
                "Selected flight origin_city must match the requested departure_city."
            )
        if hotel.check_in != request.start_date or hotel.check_out != request.end_date:
            raise ValueError("Accommodation dates must match the requested trip dates.")
        if hotel.nights != request.nights:
            raise ValueError("Accommodation nights must match the requested trip nights.")
        if hotel.currency != request.currency:
            raise ValueError("Accommodation currency must match the requested currency.")

        if budget.currency != request.currency:
            raise ValueError("Budget breakdown currency must match the requested currency.")
        if not _approx_equal(budget.budget, request.budget):
            raise ValueError("Budget breakdown budget must match the requested budget.")
        if not _approx_equal(budget.flights, flight.price):
            raise ValueError("Budget flights must equal the selected flight price.")
        if not _approx_equal(budget.accommodation, hotel.total_price):
            raise ValueError("Budget accommodation must equal the selected accommodation total.")

        daily_food = sum(day.daily_food_estimate for day in self.daily_itinerary)
        daily_activities = sum(
            activity.estimated_cost
            for day in self.daily_itinerary
            for activity in day.activities
        )
        daily_transport = sum(day.local_transport_estimate for day in self.daily_itinerary)
        if not _approx_equal(budget.food, daily_food):
            raise ValueError("Budget food must equal the sum of daily food estimates.")
        if not _approx_equal(budget.activities, daily_activities):
            raise ValueError("Budget activities must equal the sum of scheduled activity costs.")
        if not _approx_equal(budget.local_transportation, daily_transport):
            raise ValueError(
                "Budget local_transportation must equal the sum of daily transport estimates."
            )

        if "simulat" not in self.data_disclaimer.lower():
            raise ValueError("data_disclaimer must clearly state that the data is simulated.")
        return self
