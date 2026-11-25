"""Simulated daily weather lookup tool."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from travel_agent.mock_data import date_range, resolve_city, stable_fraction, supported_destination_names
from travel_agent.schemas import MAX_TRIP_DAYS, WeatherInfo
from travel_agent.tools.errors import ToolError

TOOL_NAME = "get_weather"
TOOL_DESCRIPTION = (
    "Return deterministic SIMULATED daily weather for a supported European destination. "
    "Use it for every day of the trip. The data is mock data, not a live forecast."
)


class WeatherQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(min_length=1)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "WeatherQuery":
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date.")
        if (self.end_date - self.start_date).days + 1 > MAX_TRIP_DAYS:
            raise ValueError(f"Date range cannot exceed {MAX_TRIP_DAYS} days.")
        return self


def _condition_for(precipitation_probability: int) -> str:
    if precipitation_probability >= 65:
        return "Light rain"
    if precipitation_probability >= 50:
        return "Cloudy with a chance of showers"
    if precipitation_probability >= 35:
        return "Partly cloudy"
    return "Sunny"


def get_weather(destination: str, start_date: date, end_date: date) -> dict[str, Any]:
    """Return simulated weather for each date in the inclusive range."""
    if end_date < start_date:
        raise ToolError("end_date cannot be earlier than start_date.")
    if (end_date - start_date).days + 1 > MAX_TRIP_DAYS:
        raise ToolError(f"Date range cannot exceed {MAX_TRIP_DAYS} days.")

    city = resolve_city(destination)
    if city is None:
        supported = ", ".join(supported_destination_names())
        raise ToolError(
            f"Unsupported destination for simulated weather: '{destination}'. "
            f"Supported destinations: {supported}."
        )

    days: list[dict[str, Any]] = []
    for day in date_range(start_date, end_date):
        climate = city.climate[day.month - 1]
        variation = stable_fraction("weather", city.key, day.isoformat())
        temperature_swing = int(variation * 5) - 2
        precipitation = max(
            0,
            min(100, climate.rain_probability + int(variation * 21) - 10),
        )
        weather = WeatherInfo(
            date=day,
            condition=_condition_for(precipitation),
            min_temp_c=climate.low_c + temperature_swing,
            max_temp_c=climate.high_c + temperature_swing,
            precipitation_probability=precipitation,
        )
        days.append(weather.model_dump(mode="json"))

    return {
        "simulated": True,
        "destination": city.name,
        "country": city.country,
        "days": days,
        "note": (
            "SIMULATED seasonal weather data. It is not a forecast and must not be "
            "presented as verified real-world information."
        ),
    }
