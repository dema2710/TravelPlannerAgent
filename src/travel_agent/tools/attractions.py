"""Simulated attractions and dining search tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from travel_agent.mock_data import (
    AttractionSeed,
    DIETARY_ALIASES,
    INTEREST_ALIASES,
    normalize_dietary_restriction,
    normalize_interest,
    resolve_city,
    supported_destination_names,
)
from travel_agent.schemas import Attraction
from travel_agent.tools.errors import ToolError
from travel_agent.utils.money import convert_from_eur, normalize_currency

TOOL_NAME = "search_attractions"
TOOL_DESCRIPTION = (
    "Search a deterministic SIMULATED catalogue of attractions, activities, and "
    "restaurants for a supported destination. Filter by interests and dietary needs. "
    "Use returned prices and IDs when building the itinerary."
)

TOOL_NOTE = (
    "SIMULATED catalogue with illustrative prices and fictional restaurant names. "
    "Opening hours and availability are not verified."
)


class AttractionSearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(min_length=1)
    interests: list[str] = Field(min_length=1)
    dietary_preferences: list[str] = Field(default_factory=list)
    currency: str = "EUR"

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("interests", "dietary_preferences")
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            normalized = " ".join(value.strip().lower().split())
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned


def _to_attraction(seed: AttractionSeed, index: int, city_key: str, currency: str) -> Attraction:
    opening_hours = (
        f"{seed.opening_hours[0]}-{seed.opening_hours[1]}" if seed.opening_hours else None
    )
    return Attraction(
        attraction_id=f"AT-{city_key[:3].upper()}-{index:02d}",
        name=seed.name,
        category=seed.category,
        description=seed.description,
        duration_hours=seed.duration_hours,
        price=convert_from_eur(seed.price_eur, currency),
        currency=currency,
        opening_hours=opening_hours,
        closed_weekdays=list(seed.closed_weekdays),
        interests=list(seed.interests),
        dietary_tags=list(seed.dietary_tags),
        meal_type=seed.meal_type,  # type: ignore[arg-type]
        location=seed.location,
    )


def search_attractions(
    destination: str,
    interests: list[str],
    dietary_preferences: list[str] | None = None,
    currency: str = "EUR",
) -> dict[str, Any]:
    """Return simulated attractions matching interests and dietary preferences."""
    city = resolve_city(destination)
    if city is None:
        supported = ", ".join(supported_destination_names())
        raise ToolError(
            f"Unsupported destination for simulated attractions: '{destination}'. "
            f"Supported destinations: {supported}."
        )

    requested_interests = interests
    normalized_interests = [
        normalized
        for interest in interests
        if (normalized := normalize_interest(interest)) is not None
    ]
    if not normalized_interests:
        supported_interests = ", ".join(sorted(INTEREST_ALIASES))
        raise ToolError(
            "None of the requested interests are supported by the simulated catalogue. "
            f"Try broader interests such as: {supported_interests}."
        )
    normalized_interests = list(dict.fromkeys(normalized_interests))

    raw_restrictions = dietary_preferences or []
    normalized_restrictions: list[str] = []
    unapplied_restrictions: list[str] = []
    for restriction in raw_restrictions:
        normalized = normalize_dietary_restriction(restriction)
        if normalized is None:
            unapplied_restrictions.append(restriction)
        elif normalized not in normalized_restrictions:
            normalized_restrictions.append(normalized)

    matches: list[tuple[int, int, Attraction]] = []
    for index, seed in enumerate(city.attractions):
        relevance = sum(1 for interest in seed.interests if interest in normalized_interests)
        # A dietary requirement is itself a reason to surface compatible dining options.
        if relevance == 0 and not (seed.category == "food" and normalized_restrictions):
            continue

        if seed.category == "food" and normalized_restrictions:
            if any(restriction not in seed.dietary_tags for restriction in normalized_restrictions):
                continue

        attraction = _to_attraction(seed, index + 1, city.key, currency)
        matches.append((relevance, index, attraction))

    if not matches:
        dietary_hint = ""
        if normalized_restrictions:
            dietary_hint = (
                " Consider searching again with broader interests or fewer dietary "
                "restrictions, or note the limitation in the plan."
            )
        raise ToolError(
            f"The simulated catalogue returned no attractions for destination '{city.name}' "
            f"and interests {requested_interests}.{dietary_hint}"
        )

    matches.sort(key=lambda item: (-item[0], item[1]))
    attractions = [item[2] for item in matches]

    return {
        "simulated": True,
        "destination": city.name,
        "currency": currency,
        "matched_interests": normalized_interests,
        "dietary_filter": normalized_restrictions,
        "restaurants_are_informational_only": True,
        "attractions": [attraction.model_dump(mode="json") for attraction in attractions],
        "unapplied_dietary_preferences": unapplied_restrictions,
        "note": TOOL_NOTE,
    }
