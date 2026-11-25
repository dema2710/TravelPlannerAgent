"""Simulated accommodation search tool."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from travel_agent.mock_data import resolve_city, season_factor, stable_fraction, supported_destination_names
from travel_agent.schemas import AccommodationOption
from travel_agent.tools.errors import ToolError
from travel_agent.utils.money import convert_from_eur, normalize_currency, round_money

TOOL_NAME = "search_accommodation"
TOOL_DESCRIPTION = (
    "Search deterministic SIMULATED accommodation for a destination and date range. "
    "Returns available hotel options with total prices, sorted by total price. "
    "Optionally pass a maximum nightly budget."
)


class AccommodationSearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(min_length=1)
    check_in: date
    check_out: date
    budget_per_night: float | None = Field(default=None, gt=0)
    currency: str = "EUR"

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("budget_per_night")
    @classmethod
    def validate_budget(cls, value: float | None) -> float | None:
        return None if value is None else round_money(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "AccommodationSearchQuery":
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in (at least one night).")
        nights = (self.check_out - self.check_in).days
        if nights > 14:
            raise ValueError("Simulated stays are limited to 14 nights.")
        return self


def search_accommodation(
    destination: str,
    check_in: date,
    check_out: date,
    budget_per_night: float | None = None,
    currency: str = "EUR",
) -> dict[str, Any]:
    """Return simulated accommodation options sorted by total price."""
    city = resolve_city(destination)
    if city is None:
        supported = ", ".join(supported_destination_names())
        raise ToolError(
            f"Unsupported destination for simulated accommodation: '{destination}'. "
            f"Supported destinations: {supported}."
        )

    nights = (check_out - check_in).days
    if nights <= 0:
        raise ToolError("check_out must be after check_in.")

    seasonal = season_factor(check_in)
    options: list[AccommodationOption] = []
    for index, hotel in enumerate(city.hotels, start=1):
        variation = 0.96 + stable_fraction("hotel", city.key, index, check_in) * 0.08
        nightly_eur = hotel.base_price_per_night_eur * seasonal * variation
        nightly = convert_from_eur(nightly_eur, currency)
        total = round_money(nightly * nights)
        option = AccommodationOption(
            hotel_id=f"HT-{city.airport_code}-{index:02d}",
            name=hotel.name,
            category=hotel.category,
            location=f"{hotel.location}, {city.name}",
            rating=hotel.rating,
            check_in=check_in,
            check_out=check_out,
            price_per_night=nightly,
            nights=nights,
            total_price=total,
            currency=currency,
        )
        options.append(option)

    options.sort(key=lambda option: (option.total_price, -option.rating))
    if budget_per_night is not None:
        options = [
            option for option in options if option.price_per_night <= budget_per_night + 0.001
        ]
        if not options:
            cheapest = min(
                convert_from_eur(
                    hotel.base_price_per_night_eur
                    * seasonal
                    * (0.96 + stable_fraction("hotel", city.key, index, check_in) * 0.08),
                    currency,
                )
                for index, hotel in enumerate(city.hotels, start=1)
            )
            raise ToolError(
                f"No simulated accommodation was found at or below {budget_per_night:.2f} "
                f"{currency} per night. The lowest simulated nightly rate is approximately "
                f"{cheapest:.2f} {currency}. Retry without a nightly budget."
            )

    return {
        "simulated": True,
        "destination": city.name,
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "nights": nights,
        "currency": currency,
        "options": [option.model_dump(mode="json") for option in options],
        "note": (
            "SIMULATED accommodation inventory with fictional property names. "
            "Rooms are not available for booking."
        ),
    }
