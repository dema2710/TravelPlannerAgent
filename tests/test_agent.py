"""Offline tests for the explicit agent loop, error recovery, and tracing."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from travel_agent.agent import AgentError, TravelAgent
from travel_agent.llm_client import (
    LLMError,
    LLMResponse,
    LLMToolCall,
    ScriptedOfflineLLM,
)
from travel_agent.schemas import TravelPlan, TravelRequest
from travel_agent.tools import build_default_registry
from travel_agent.utils.trace_logger import TraceLogger


class QueueLLM:
    """Test double returning a fixed queue of normalised LLM responses."""

    provider_name = "test"
    model_name = "queue"

    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        self.responses = list(responses)
        self.received_messages: list[list[dict[str, Any]]] = []

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        del tools
        self.received_messages.append(deepcopy(messages))
        if not self.responses:
            raise AssertionError("The fake LLM ran out of queued responses.")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class RepeatingWeatherLLM:
    """Test double that keeps requesting one tool to exercise the iteration bound."""

    provider_name = "test"
    model_name = "repeating"

    def __init__(self) -> None:
        self.calls = 0

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        del messages, tools
        self.calls += 1
        return LLMResponse(
            content=None,
            tool_calls=[
                LLMToolCall(
                    id=f"call-{self.calls}",
                    name="get_weather",
                    arguments=json.dumps(
                        {
                            "destination": "Paris",
                            "start_date": "2027-05-10",
                            "end_date": "2027-05-12",
                        }
                    ),
                )
            ],
            metadata={"finish_reason": "tool_calls"},
        )


def _tool_call(call_id: str, name: str, arguments: str) -> LLMToolCall:
    return LLMToolCall(id=call_id, name=name, arguments=arguments)


def _tool_response(*calls: LLMToolCall) -> LLMResponse:
    return LLMResponse(content=None, tool_calls=list(calls), metadata={"finish_reason": "tool_calls"})


def _final_payload(plan: TravelPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False)


def _read_events(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines
    return [json.loads(line) for line in lines]


def test_offline_agent_completes_and_writes_structured_trace(
    tmp_path: Path,
    paris_request: TravelRequest,
) -> None:
    trace_path = tmp_path / "offline_trace.jsonl"
    trace = TraceLogger(trace_path, run_id="test-run", mode="offline_simulated")
    progress: list[str] = []
    try:
        agent = TravelAgent(
            llm=ScriptedOfflineLLM(paris_request),
            registry=build_default_registry(),
            max_iterations=10,
            trace=trace,
            progress=progress.append,
        )
        plan = agent.run(paris_request)
    finally:
        trace.close()

    assert plan.budget_breakdown.budget_respected is True
    assert plan.budget_breakdown.total_estimated_cost <= paris_request.budget
    assert plan.request.departure_city == "Prague"
    assert plan.selected_flight.origin_city == "Prague"
    assert plan.selected_flight.destination_city == "Paris"
    assert len(plan.daily_itinerary) == 3
    assert any("[Tool] get_weather completed" in line for line in progress)

    events = _read_events(trace_path)
    event_names = [event["event"] for event in events]
    assert event_names[0] == "run_started"
    assert "llm_request" in event_names
    assert "llm_response" in event_names
    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert "final_output" in event_names
    assert event_names[-1] == "run_finished"
    assert events[-1]["status"] == "success"
    assert events[0]["mode"] == "offline_simulated"

    initial_responses = [
        event for event in events if event["event"] == "llm_response"
    ]
    assert any(len(response["tool_calls"]) == 4 for response in initial_responses)

    accepted = [event for event in events if event["event"] == "final_output"]
    assert accepted[-1]["status"] == "accepted"
    assert accepted[-1]["plan"]["request"]["destination"] == "Paris"

    flight_calls = [
        event
        for event in events
        if event["event"] == "tool_call" and event["tool"] == "search_flights"
    ]
    assert flight_calls
    flight_arguments = json.loads(flight_calls[0]["arguments"])
    assert flight_arguments["departure_city"] == paris_request.departure_city
    assert flight_arguments["destination"] == "Paris"


def test_agent_handles_unknown_tool_and_malformed_arguments(
    tmp_path: Path,
    paris_request: TravelRequest,
    paris_plan: TravelPlan,
) -> None:
    llm = QueueLLM(
        [
            _tool_response(
                _tool_call("bad-1", "made_up_tool", "{}"),
                _tool_call("bad-2", "get_weather", '{"destination": '),
            ),
            LLMResponse(content=_final_payload(paris_plan)),
        ]
    )
    trace_path = tmp_path / "tool_errors.jsonl"
    trace = TraceLogger(trace_path, run_id="errors-run", mode="offline_simulated")
    try:
        agent = TravelAgent(
            llm=llm,
            registry=build_default_registry(),
            max_iterations=4,
            trace=trace,
        )
        plan = agent.run(paris_request)
    finally:
        trace.close()

    assert isinstance(plan, TravelPlan)
    events = _read_events(trace_path)
    errors = [event for event in events if event["event"] == "tool_error"]
    assert {event["error_type"] for event in errors} == {"unknown_tool", "invalid_arguments"}
    assert events[-1]["status"] == "success"
    assert len(llm.received_messages) == 2

    second_messages = llm.received_messages[1]
    tool_messages = [message for message in second_messages if message["role"] == "tool"]
    assert len(tool_messages) == 2
    assert all(json.loads(message["content"])["ok"] is False for message in tool_messages)


def test_agent_repairs_invalid_json_before_accepting(
    tmp_path: Path,
    paris_request: TravelRequest,
    paris_plan: TravelPlan,
) -> None:
    llm = QueueLLM(
        [
            LLMResponse(content="This is not JSON."),
            LLMResponse(content=_final_payload(paris_plan)),
        ]
    )
    trace_path = tmp_path / "repair.jsonl"
    trace = TraceLogger(trace_path, run_id="repair-run", mode="offline_simulated")
    try:
        agent = TravelAgent(
            llm=llm,
            registry=build_default_registry(),
            max_iterations=4,
            trace=trace,
        )
        plan = agent.run(paris_request)
    finally:
        trace.close()

    assert isinstance(plan, TravelPlan)
    events = _read_events(trace_path)
    rejected = [
        event
        for event in events
        if event["event"] == "final_output" and event["status"] == "rejected"
    ]
    assert rejected
    assert "JSON object" in rejected[0]["error"]
    assert events[-1]["status"] == "success"
    correction = llm.received_messages[1][-1]["content"]
    assert "rejected by schema validation" in correction


def test_agent_rejects_over_budget_claim_then_repairs(
    tmp_path: Path,
    paris_request: TravelRequest,
    paris_plan: TravelPlan,
) -> None:
    bad_payload = deepcopy(paris_plan.model_dump(mode="json"))
    total = bad_payload["budget_breakdown"]["total_estimated_cost"]
    lower_budget = round(total - 100, 2)
    bad_payload["request"]["budget"] = lower_budget
    bad_payload["budget_breakdown"]["budget"] = lower_budget
    bad_payload["budget_breakdown"]["remaining_budget"] = round(lower_budget - total, 2)
    bad_payload["budget_breakdown"]["budget_respected"] = True  # false over-budget claim
    llm = QueueLLM(
        [
            LLMResponse(content=json.dumps(bad_payload)),
            LLMResponse(content=_final_payload(paris_plan)),
        ]
    )
    trace_path = tmp_path / "budget_repair.jsonl"
    trace = TraceLogger(trace_path, run_id="budget-run", mode="offline_simulated")
    try:
        agent = TravelAgent(
            llm=llm,
            registry=build_default_registry(),
            max_iterations=4,
            trace=trace,
        )
        plan = agent.run(paris_request)
    finally:
        trace.close()

    assert plan.budget_breakdown.budget_respected is True
    events = _read_events(trace_path)
    rejected = [
        event
        for event in events
        if event["event"] == "final_output" and event["status"] == "rejected"
    ]
    assert rejected
    assert "budget_respected" in rejected[0]["error"]


def test_agent_rejects_modified_request_object(
    tmp_path: Path,
    paris_request: TravelRequest,
    paris_plan: TravelPlan,
) -> None:
    bad_payload = deepcopy(paris_plan.model_dump(mode="json"))
    bad_payload["request"]["destination"] = "Berlin"
    llm = QueueLLM(
        [
            LLMResponse(content=json.dumps(bad_payload)),
            LLMResponse(content=_final_payload(paris_plan)),
        ]
    )
    trace_path = tmp_path / "request_mismatch.jsonl"
    trace = TraceLogger(trace_path, run_id="request-run", mode="offline_simulated")
    try:
        agent = TravelAgent(
            llm=llm,
            registry=build_default_registry(),
            max_iterations=4,
            trace=trace,
        )
        plan = agent.run(paris_request)
    finally:
        trace.close()

    assert plan.request == paris_request
    events = _read_events(trace_path)
    rejected = [
        event
        for event in events
        if event["event"] == "final_output" and event["status"] == "rejected"
    ]
    assert rejected
    assert "exactly match" in rejected[0]["error"]


def test_agent_stops_at_maximum_iterations(
    tmp_path: Path,
    paris_request: TravelRequest,
) -> None:
    llm = RepeatingWeatherLLM()
    trace_path = tmp_path / "max_iterations.jsonl"
    trace = TraceLogger(trace_path, run_id="max-run", mode="offline_simulated")
    try:
        agent = TravelAgent(
            llm=llm,
            registry=build_default_registry(),
            max_iterations=3,
            trace=trace,
        )
        with pytest.raises(AgentError, match="3 iterations"):
            agent.run(paris_request)
    finally:
        trace.close()

    assert llm.calls == 3
    events = _read_events(trace_path)
    assert events[-1]["event"] == "run_finished"
    assert events[-1]["status"] == "error"
    assert len([event for event in events if event["event"] == "tool_call"]) == 3


def test_agent_handles_llm_connection_failure_gracefully(
    tmp_path: Path,
    paris_request: TravelRequest,
) -> None:
    llm = QueueLLM([LLMError("Could not connect to DeepSeek.")])
    trace_path = tmp_path / "llm_error.jsonl"
    trace = TraceLogger(trace_path, run_id="llm-error-run", mode="offline_simulated")
    try:
        agent = TravelAgent(
            llm=llm,
            registry=build_default_registry(),
            max_iterations=3,
            trace=trace,
        )
        with pytest.raises(AgentError, match="Could not connect"):
            agent.run(paris_request)
    finally:
        trace.close()

    events = _read_events(trace_path)
    assert events[-1]["status"] == "error"
    assert events[-1]["error_type"] == "AgentError"


def test_agent_accepts_structured_error_response(
    tmp_path: Path,
    paris_request: TravelRequest,
) -> None:
    llm = QueueLLM(
        [LLMResponse(content='{"error": "No feasible plan exists for this budget."}')]
    )
    trace_path = tmp_path / "structured_error.jsonl"
    trace = TraceLogger(trace_path, run_id="structured-error-run", mode="offline_simulated")
    try:
        agent = TravelAgent(
            llm=llm,
            registry=build_default_registry(),
            max_iterations=3,
            trace=trace,
        )
        with pytest.raises(AgentError, match="No feasible plan"):
            agent.run(paris_request)
    finally:
        trace.close()

    events = _read_events(trace_path)
    assert events[-1]["status"] == "error"


def test_scripted_offline_client_replans_when_first_itinerary_is_over_budget(
    tmp_path: Path,
    prague_request: TravelRequest,
) -> None:
    tight_request = prague_request.model_copy(update={"budget": 440.0})
    trace_path = tmp_path / "replanning.jsonl"
    trace = TraceLogger(trace_path, run_id="replanning-run", mode="offline_simulated")
    try:
        agent = TravelAgent(
            llm=ScriptedOfflineLLM(tight_request),
            registry=build_default_registry(),
            max_iterations=10,
            trace=trace,
        )
        plan = agent.run(tight_request)
    finally:
        trace.close()

    assert plan.budget_breakdown.budget_respected is True
    assert plan.budget_breakdown.remaining_budget >= 0
    assert plan.request.departure_city == "Berlin"
    assert plan.selected_flight.origin_city == "Berlin"
    assert plan.selected_flight.destination_city == "Prague"

    events = _read_events(trace_path)
    planner_calls = [
        event
        for event in events
        if event["event"] == "tool_call" and event["tool"] == "create_daily_itinerary"
    ]
    assert len(planner_calls) == 2
    assert events[-1]["status"] == "success"
