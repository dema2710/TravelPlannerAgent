"""Simulated round-trip flight search tool."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from travel_agent.mock_data import (
    AIRLINES,
    DEFAULT_DEPARTURE_CITY,
    DESTINATION_TIMEZONE_OFFSET_MINUTES,
    add_minutes,
    resolve_city,
    resolve_departure_city,
    route_flight_minutes,
    season_factor,
    stable_fraction,
    supported_departure_names,
    supported_destination_names,
)
from travel_agent.schemas import FlightOption
from travel_agent.tools.errors import ToolError
from travel_agent.utils.money import convert_from_eur, normalize_currency, round_money

TOOL_NAME = "search_flights"
TOOL_DESCRIPTION = (
    "Search deterministic SIMULATED round-trip economy flights for one traveller "
    "between a supported departure city (Prague, Berlin, Vienna, or London) and a "
    "supported European destination. departure_city defaults to Prague. "
    "Optionally pass the maximum flight budget. Returns options sorted by price."
)


class FlightSearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(min_length=1)
    departure_city: str = Field(default=DEFAULT_DEPARTURE_CITY, min_length=1)
    departure_date: date
    return_date: date
    budget: float | None = Field(default=None, gt=0)
    currency: str = "EUR"

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

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, value: float | None) -> float | None:
        return None if value is None else round_money(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "FlightSearchQuery":
        if self.return_date < self.departure_date:
            raise ValueError("return_date cannot be earlier than departure_date.")
        if (self.return_date - self.departure_date).days > 14:
            raise ValueError("Simulated flights are limited to trips of up to 15 days.")
        return self


def _arrival_time(departure_time: str, flight_minutes: int, timezone_offset: int) -> str:
    return add_minutes(departure_time, flight_minutes + timezone_offset)


def search_flights(
    destination: str,
    departure_date: date,
    return_date: date,
    budget: float | None = None,
    currency: str = "EUR",
    departure_city: str = DEFAULT_DEPARTURE_CITY,
) -> dict[str, Any]:
    """Return simulated flight options sorted by total round-trip price.

    ``departure_city`` is appended after the original parameters so existing
    positional callers keep their previous meaning for ``budget`` and ``currency``.
    """
    if return_date < departure_date:
        raise ToolError("return_date cannot be earlier than departure_date.")
    if (return_date - departure_date).days > 14:
        raise ToolError("Simulated flights are limited to trips of up to 15 days.")

    origin = resolve_departure_city(departure_city)
    if origin is None:
        supported = ", ".join(supported_departure_names())
        raise ToolError(
            f"Unsupported departure city for simulated flights: '{departure_city}'. "
            f"Supported departure cities: {supported}."
        )

    city = resolve_city(destination)
    if city is None:
        supported = ", ".join(supported_destination_names())
        raise ToolError(
            f"Unsupported destination for simulated flights: '{destination}'. "
            f"Supported destinations: {supported}."
        )
    if origin.key == city.key:
        raise ToolError(
            f"Departure city and destination are both {city.name}. "
            "Choose a different departure_city for the flight search."
        )

    seasonal = season_factor(departure_date)
    route_minutes = route_flight_minutes(origin, city)
    timezone_delta = DESTINATION_TIMEZONE_OFFSET_MINUTES - origin.timezone_offset_minutes
    options: list[FlightOption] = []

    for index, airline in enumerate(AIRLINES, start=1):
        variation = (
            0.94
            + stable_fraction(
                "flight",
                origin.key,
                city.key,
                index,
                departure_date,
            )
            * 0.12
        )
        price_eur = (
            city.flight_base_eur
            * origin.price_factor
            * seasonal
            * float(airline["price_factor"])
            * variation
        )
        price = convert_from_eur(price_eur, currency)
        outbound = str(airline["outbound_departure"])
        inbound = str(airline["return_departure"])
        option = FlightOption(
            flight_id=f"FL-{origin.airport_code}-{city.airport_code}-{index:02d}",
            airline=str(airline["name"]),
            origin_city=origin.name,
            origin_airport=origin.airport_code,
            destination_city=city.name,
            destination_airport=city.airport_code,
            departure_date=departure_date,
            return_date=return_date,
            outbound_departure_time=outbound,
            outbound_arrival_time=_arrival_time(outbound, route_minutes, timezone_delta),
            return_departure_time=inbound,
            return_arrival_time=_arrival_time(inbound, route_minutes, -timezone_delta),
            stops=int(airline["stops"]),
            price=price,
            currency=currency,
        )
        options.append(option)

    options.sort(key=lambda option: (option.price, option.stops))
    if budget is not None:
        options = [option for option in options if option.price <= budget + 0.001]
        if not options:
            cheapest = min(
                convert_from_eur(
                    city.flight_base_eur
                    * origin.price_factor
                    * seasonal
                    * float(airline["price_factor"]),
                    currency,
                )
                for airline in AIRLINES
            )
            raise ToolError(
                f"No simulated flight was found at or below {budget:.2f} {currency}. "
                f"The lowest simulated fare from {origin.name} is approximately "
                f"{cheapest:.2f} {currency}. Retry without a flight budget to inspect "
                "all options."
            )

    return {
        "simulated": True,
        "departure_city": origin.name,
        "destination_city": city.name,
        "origin": f"{origin.name} ({origin.airport_code})",
        "destination": f"{city.name} ({city.airport_code})",
        "travellers": 1,
        "currency": currency,
        "options": [option.model_dump(mode="json") for option in options],
        "note": (
            "SIMULATED fares and schedules for one traveller. No seats are held and no "
            "booking is possible. Departure and arrival airports are shown in every option."
        ),
    }
