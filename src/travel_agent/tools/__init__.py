"""The five simulated tools exposed to the agent."""

from __future__ import annotations

from travel_agent.tools.accommodation import (
    AccommodationSearchQuery,
    TOOL_DESCRIPTION as ACCOMMODATION_DESCRIPTION,
    TOOL_NAME as ACCOMMODATION_NAME,
    search_accommodation,
)
from travel_agent.tools.attractions import (
    AttractionSearchQuery,
    TOOL_DESCRIPTION as ATTRACTIONS_DESCRIPTION,
    TOOL_NAME as ATTRACTIONS_NAME,
    search_attractions,
)
from travel_agent.tools.flights import (
    FlightSearchQuery,
    TOOL_DESCRIPTION as FLIGHTS_DESCRIPTION,
    TOOL_NAME as FLIGHTS_NAME,
    search_flights,
)
from travel_agent.tools.planner import (
    TOOL_DESCRIPTION as PLANNER_DESCRIPTION,
    TOOL_NAME as PLANNER_NAME,
    ItineraryQuery,
    create_daily_itinerary,
)
from travel_agent.tools.registry import ToolDefinition, ToolExecution, ToolRegistry
from travel_agent.tools.weather import (
    TOOL_DESCRIPTION as WEATHER_DESCRIPTION,
    TOOL_NAME as WEATHER_NAME,
    WeatherQuery,
    get_weather,
)

__all__ = [
    "ToolDefinition",
    "ToolExecution",
    "ToolRegistry",
    "build_default_registry",
]


def build_default_registry() -> ToolRegistry:
    """Create a registry containing the five assignment tools."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name=WEATHER_NAME,
            description=WEATHER_DESCRIPTION,
            input_model=WeatherQuery,
            handler=get_weather,
        )
    )
    registry.register(
        ToolDefinition(
            name=FLIGHTS_NAME,
            description=FLIGHTS_DESCRIPTION,
            input_model=FlightSearchQuery,
            handler=search_flights,
        )
    )
    registry.register(
        ToolDefinition(
            name=ACCOMMODATION_NAME,
            description=ACCOMMODATION_DESCRIPTION,
            input_model=AccommodationSearchQuery,
            handler=search_accommodation,
        )
    )
    registry.register(
        ToolDefinition(
            name=ATTRACTIONS_NAME,
            description=ATTRACTIONS_DESCRIPTION,
            input_model=AttractionSearchQuery,
            handler=search_attractions,
        )
    )
    registry.register(
        ToolDefinition(
            name=PLANNER_NAME,
            description=PLANNER_DESCRIPTION,
            input_model=ItineraryQuery,
            handler=create_daily_itinerary,
        )
    )
    return registry
