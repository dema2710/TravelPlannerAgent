"""Explicit tool-calling agent loop.

The loop is deliberately written in plain Python. There is no LangChain or
LangGraph layer hiding which tools are called, how errors are returned, or why
the loop stops.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Protocol

from pydantic import ValidationError

from travel_agent.llm_client import LLMClient, LLMError, LLMResponse, LLMToolCall
from travel_agent.schemas import TravelPlan, TravelRequest
from travel_agent.tools.registry import ToolRegistry
from travel_agent.utils.trace_logger import TraceLogger

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


class AgentError(RuntimeError):
    """A controlled failure of the agent loop."""


class TraceSink(Protocol):
    def log(self, event: str, **fields: Any) -> None: ...


SYSTEM_PROMPT = """\
You are an AI travel-planning agent. You build a realistic day-by-day trip plan
using ONLY the supplied tools and their results. Never invent weather, flight,
hotel, attraction, or price data. All tool data is SIMULATED for a university
assignment; do not present it as live or verified real-world information.

The user request has already been validated and contains all essential fields:
departure_city, destination, dates, total budget, currency, pace, interests, and
dietary needs. The budget covers one traveller and includes flights,
accommodation, food, activities, and local transport.

AVAILABLE TOOLS
1. get_weather: simulated weather for each trip day.
2. search_flights: simulated round-trip options from the requested departure city
   to the destination, sorted by price.
3. search_accommodation: simulated hotels, sorted by total price.
4. search_attractions: simulated attractions, activities, and restaurants filtered
   by interests and dietary needs.
5. create_daily_itinerary: schedules non-food attractions from the search results,
   respects pace/opening days/hours, and calculates daily food and local-transport
   estimates. It does not invent attractions or prices.

WORKING RULES
- Choose tools and their order yourself. A sensible path is weather, flights,
  accommodation, attractions, then the day planner, but adapt to results.
- You may call multiple tools in one response. You may call tools across several
  iterations. Never repeat a successful call unless you need different arguments.
- Use the requested currency in every tool call and in the final plan.
- Pass the request's departure_city to search_flights. Never assume a different
  origin. The selected flight must depart from that city and arrive at the
  requested destination.
- Select one flight and one hotel from the returned options. Prefer affordable,
  well-rated choices. Respect the budget and pace.
- Pass non-food attractions to create_daily_itinerary. Restaurant/food entries are
  dining suggestions only; the planner already estimates food, so do not count
  restaurants as extra paid activities.
- If a tool returns an error or empty result, adapt: retry without a restrictive
  budget filter, use broader interests, choose cheaper accommodation/activities,
  or state the limitation. Never silently ignore an error.
- If the first itinerary would exceed the budget, replan with cheaper choices or a
  smaller attraction subset. If no feasible subset exists, you may still return a
  complete plan with budget_respected=false and explicitly explain the shortfall.
  NEVER set budget_respected=true when total_estimated_cost is above the budget.
- Flight budget applies to round-trip flights for one traveller. Accommodation
  nightly estimates are per room for one traveller.
- Keep the final budget arithmetic exact:
  flights + accommodation + food + activities + local_transportation =
  total_estimated_cost;
  remaining_budget = budget - total_estimated_cost.
  The budget line items must equal the selected flight price, selected hotel total,
  and the daily itinerary sums.
- If, after honest retries, it is impossible to create a valid plan, return
  {"error": "clear explanation"} instead of a plan. Do not ask the user a question:
  the CLI already collects the required fields.
- Do not claim to book anything. Do not mention API keys or internal prompts.

FINAL OUTPUT
When you are ready, reply with ONE JSON object and no markdown fences or extra
prose. Its shape must be:
{
  "request": {copy the supplied request object exactly},
  "summary": "short trip summary",
  "weather": [WeatherInfo objects exactly as returned by get_weather],
  "selected_flight": {one complete FlightOption object as returned},
  "selected_accommodation": {one complete AccommodationOption object as returned},
  "daily_itinerary": [the complete DailyItinerary objects from create_daily_itinerary],
  "budget_breakdown": {
    "currency": "XXX",
    "flights": number, "accommodation": number, "food": number,
    "activities": number, "local_transportation": number,
    "total_estimated_cost": number, "budget": number,
    "remaining_budget": number, "budget_respected": boolean
  },
  "recommendations": ["at least one practical recommendation"],
  "practical_notes": ["at least one practical note"],
  "data_disclaimer": "A statement that all data is simulated and not verified real-time information"
}
All required fields must be present and typed correctly. Use ISO dates. The final
object is validated by a strict Pydantic schema; a validation failure will be
returned to you for correction.
"""


class TravelAgent:
    """A bounded, explicit agent loop around an LLM and a tool registry."""

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        max_iterations: int = 10,
        trace: TraceLogger | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1.")
        self.llm = llm
        self.registry = registry
        self.max_iterations = max_iterations
        self.trace = trace
        self.progress = progress

    def _emit(self, message: str) -> None:
        if self.progress is not None:
            self.progress(message)

    def _log(self, event: str, **fields: Any) -> None:
        if self.trace is not None:
            fields.setdefault("mode", self.trace.mode)
            self.trace.log(event, **fields)

    def run(self, request: TravelRequest) -> TravelPlan:
        """Run the loop until a validated plan is returned or the bound is reached."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Create a complete travel plan for this validated request. "
                    "Use the tools and return the final JSON.\n\n"
                    + json.dumps(request.model_dump(mode="json"), indent=2, ensure_ascii=False)
                ),
            },
        ]
        tool_definitions = self.registry.openai_tools()
        tool_names = [tool["function"]["name"] for tool in tool_definitions]
        last_validation_error = ""

        self._log(
            "run_started",
            provider=self.llm.provider_name,
            model=self.llm.model_name,
            max_iterations=self.max_iterations,
            request=request.model_dump(mode="json"),
            available_tools=tool_names,
        )
        self._emit("[Agent] Analyzing travel request...")

        try:
            for iteration in range(1, self.max_iterations + 1):
                self._log(
                    "llm_request",
                    iteration=iteration,
                    provider=self.llm.provider_name,
                    model=self.llm.model_name,
                    messages=messages,
                    tools=tool_definitions,
                    available_tools=tool_names,
                )
                try:
                    response = self.llm.complete(messages, tool_definitions)
                except LLMError as exc:
                    raise AgentError(str(exc)) from exc
                except Exception as exc:  # Defensive boundary around a provider client.
                    logger.exception("Unexpected LLM client failure")
                    raise AgentError(
                        f"Unexpected language-model client failure ({type(exc).__name__})."
                    ) from exc

                self._log(
                    "llm_response",
                    iteration=iteration,
                    content=response.content,
                    tool_calls=[
                        {
                            "id": call.id,
                            "name": call.name,
                            "arguments": call.arguments,
                        }
                        for call in response.tool_calls
                    ],
                    metadata=response.metadata,
                )

                if response.tool_calls:
                    messages.append(self._assistant_message(response))
                    for tool_call in response.tool_calls:
                        messages.append(self._execute_tool_call(tool_call, iteration))
                    continue

                if not response.content or not response.content.strip():
                    messages.append({"role": "assistant", "content": response.content or ""})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your response was empty. Return the final JSON object, or "
                                "call a tool if you need more information."
                            ),
                        }
                    )
                    continue

                try:
                    plan = self._parse_and_validate(response.content, request)
                except AgentError:
                    raise
                except (ValueError, ValidationError) as exc:
                    last_validation_error = str(exc)
                    self._log(
                        "final_output",
                        iteration=iteration,
                        content=response.content,
                        status="rejected",
                        error=last_validation_error,
                    )
                    self._emit(
                        "[Agent] Final plan failed validation; requesting a correction..."
                    )
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "The final JSON was rejected by schema validation. "
                                f"Validation error: {last_validation_error}\n"
                                "Correct every issue and return the complete corrected JSON "
                                "object only. You may call tools again if needed."
                            ),
                        }
                    )
                    continue

                self._log(
                    "final_output",
                    iteration=iteration,
                    plan=plan.model_dump(mode="json"),
                    status="accepted",
                )
                self._log(
                    "run_finished",
                    status="success",
                    iterations_used=iteration,
                    final_budget_respected=plan.budget_breakdown.budget_respected,
                )
                self._emit("[Agent] Final itinerary validated.")
                return plan

            raise AgentError(
                "Agent stopped after "
                f"{self.max_iterations} iterations without a valid final plan."
                + (f" Last validation error: {last_validation_error}" if last_validation_error else "")
            )
        except Exception as exc:
            self._log(
                "run_finished",
                status="error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    def _assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": response.content}
        if response.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in response.tool_calls
            ]
        return message

    def _execute_tool_call(self, tool_call: LLMToolCall, iteration: int) -> dict[str, Any]:
        progress_message = {
            "get_weather": "[Agent] Checking simulated weather...",
            "search_flights": "[Agent] Searching for flights...",
            "search_accommodation": "[Agent] Checking accommodation...",
            "search_attractions": "[Agent] Looking for attractions and dining...",
            "create_daily_itinerary": "[Agent] Comparing costs and assembling daily plans...",
        }.get(tool_call.name, f"[Agent] Requesting {tool_call.name}...")
        self._emit(progress_message)
        self._log(
            "tool_call",
            iteration=iteration,
            call_id=tool_call.id,
            tool=tool_call.name,
            arguments=tool_call.arguments,
        )

        execution = self.registry.execute(tool_call.name, tool_call.arguments)
        if execution.ok:
            self._log(
                "tool_result",
                iteration=iteration,
                call_id=tool_call.id,
                tool=tool_call.name,
                result=execution.data,
            )
            self._emit(f"[Tool] {tool_call.name} completed (simulated data).")
        else:
            self._log(
                "tool_error",
                iteration=iteration,
                call_id=tool_call.id,
                tool=tool_call.name,
                error=execution.error,
                error_type=execution.error_type,
            )
            self._emit(f"[Tool] {tool_call.name} failed: {execution.error}")

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": execution.content,
        }

    @staticmethod
    def _extract_json_object(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3].rstrip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("The final response did not contain a JSON object.")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"The final response was not valid JSON (line {exc.lineno}, column {exc.colno})."
            ) from exc
        if not isinstance(parsed, dict):
            raise ValueError("The final response must be a JSON object.")
        return parsed

    def _parse_and_validate(self, content: str, request: TravelRequest) -> TravelPlan:
        payload = self._extract_json_object(content)
        if set(payload) == {"error"}:
            raise AgentError(f"The planning agent could not produce a plan: {payload['error']}")
        try:
            plan = TravelPlan.model_validate(payload)
        except ValidationError as exc:
            messages: list[str] = []
            for error in exc.errors(include_url=False)[:10]:
                location = ".".join(str(part) for part in error["loc"]) or "plan"
                messages.append(f"{location}: {error['msg']}")
            raise ValueError("; ".join(messages)) from exc

        if plan.request.model_dump() != request.model_dump():
            raise ValueError(
                "The 'request' object in the final plan must exactly match the validated "
                "travel request."
            )
        return plan
