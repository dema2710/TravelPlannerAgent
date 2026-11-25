"""Shared offline-only pytest fixtures."""

from __future__ import annotations

from datetime import date

import pytest

from travel_agent.agent import TravelAgent
from travel_agent.llm_client import ScriptedOfflineLLM
from travel_agent.schemas import TravelPlan, TravelRequest
from travel_agent.tools import build_default_registry


@pytest.fixture
def paris_request() -> TravelRequest:
    return TravelRequest(
        destination="Paris",
        start_date=date(2027, 5, 10),
        end_date=date(2027, 5, 12),
        budget=800.0,
        currency="EUR",
        pace="moderate",
        interests=["architecture", "museums", "history"],
        dietary_restrictions=["vegetarian"],
    )


@pytest.fixture
def prague_request() -> TravelRequest:
    return TravelRequest(
        destination="Prague",
        departure_city="Berlin",
        start_date=date(2027, 9, 3),
        end_date=date(2027, 9, 6),
        budget=480.0,
        currency="EUR",
        pace="relaxed",
        interests=["nature", "food", "history"],
        dietary_restrictions=["vegan"],
    )


@pytest.fixture
def paris_plan(paris_request: TravelRequest) -> TravelPlan:
    agent = TravelAgent(
        llm=ScriptedOfflineLLM(paris_request),
        registry=build_default_registry(),
        max_iterations=10,
    )
    return agent.run(paris_request)
