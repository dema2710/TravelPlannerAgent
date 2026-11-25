"""API-only Pydantic models.

The domain models in ``travel_agent.schemas`` remain the single source of
truth for travel requests and final plans.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from travel_agent.schemas import TravelPlan, TravelRequest

PlanMode = Literal["offline", "live"]


class APIRequest(BaseModel):
    """Base model for browser-facing API payloads."""

    model_config = ConfigDict(extra="forbid")


class ItineraryRequest(APIRequest):
    """A validated domain request plus the selected generation mode."""

    mode: PlanMode = "offline"
    request: TravelRequest


class ItineraryResponse(BaseModel):
    """A successfully generated plan and its execution metadata."""

    plan: TravelPlan
    trace_file: str
    run_id: str
    mode: PlanMode
    provider: str
    model: str


class WebConfigResponse(BaseModel):
    """Form choices and capabilities for the browser UI."""

    destinations: list[str]
    departure_cities: list[str]
    currencies: list[str]
    paces: list[str]
    interests: list[str]
    dietary_preferences: list[str]
    default_departure_city: str
    live_api_available: bool


class HealthResponse(BaseModel):
    """Minimal server health response."""

    status: Literal["ok"] = "ok"
    live_api_available: bool


class ErrorDetail(BaseModel):
    """Machine-readable and human-readable API error details."""

    code: str
    message: str
    details: list[str] = Field(default_factory=list)
    trace_file: str | None = None


class ErrorResponse(BaseModel):
    """Consistent error envelope used by the web API."""

    error: ErrorDetail
