"""LLM provider abstraction, DeepSeek client, and offline scripted client."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import openai
from openai import OpenAI

from travel_agent.config import Settings
from travel_agent.schemas import TravelRequest
from travel_agent.utils.money import round_money

OFFLINE_MODEL_NAME = "offline-scripted-fake"


class LLMError(RuntimeError):
    """A user-safe failure while contacting the LLM provider."""


@dataclass(frozen=True)
class LLMToolCall:
    """Normalised tool call returned by a provider."""

    id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    """Normalised response so the agent does not depend on SDK objects."""

    content: str | None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    """Minimal provider interface used by the agent loop."""

    provider_name: str
    model_name: str

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Return the next assistant message for the conversation."""


class DeepSeekClient:
    """DeepSeek implementation using its OpenAI-compatible Chat Completions API."""

    provider_name = "deepseek"

    def __init__(self, settings: Settings) -> None:
        if not settings.deepseek_api_key:
            raise LLMError(
                "DEEPSEEK_API_KEY is not configured. Add it to .env or run with --offline."
            )
        self.model_name = settings.model
        self._disable_thinking = settings.disable_thinking
        self._temperature = settings.temperature
        self._max_tokens = settings.max_tokens
        self._client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.base_url,
            timeout=settings.request_timeout_seconds,
            max_retries=settings.max_retries,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Call DeepSeek and normalise the assistant message."""
        request: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            request["tools"] = tools
        if self._disable_thinking:
            request["extra_body"] = {"thinking": {"type": "disabled"}}

        try:
            response = self._client.chat.completions.create(**request)
        except openai.AuthenticationError as exc:
            raise LLMError(
                "DeepSeek authentication failed. Check that DEEPSEEK_API_KEY is valid."
            ) from exc
        except openai.RateLimitError as exc:
            raise LLMError("DeepSeek rate limit reached. Wait and try again.") from exc
        except openai.APITimeoutError as exc:
            raise LLMError("DeepSeek request timed out. Try again or increase the timeout.") from exc
        except openai.APIConnectionError as exc:
            raise LLMError("Could not connect to DeepSeek. Check the network connection.") from exc
        except openai.APIStatusError as exc:
            raise LLMError(
                f"DeepSeek returned HTTP {exc.status_code}. Try again later."
            ) from exc
        except openai.OpenAIError as exc:
            raise LLMError(f"DeepSeek API error: {exc}") from exc

        if not response.choices:
            raise LLMError("DeepSeek returned no response choices.")

        choice = response.choices[0]
        message = choice.message
        tool_calls = [
            LLMToolCall(
                id=tool_call.id,
                name=tool_call.function.name,
                arguments=tool_call.function.arguments,
            )
            for tool_call in (message.tool_calls or [])
        ]
        usage = None
        if response.usage is not None:
            usage = response.usage.model_dump(mode="json")

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            metadata={
                "provider": self.provider_name,
                "model": self.model_name,
                "response_id": response.id,
                "finish_reason": choice.finish_reason,
                "usage": usage,
            },
        )


class ScriptedOfflineLLM:
    """Deterministic offline stand-in for a tool-calling LLM.

    This is intentionally simple and is used only for offline demonstrations and
    tests. It makes real tool calls, consumes the actual tool results, and
    requests a second planning pass if the first simulated total exceeds the
    budget. Offline traces are clearly labelled as scripted simulations.
    """

    provider_name = "offline_scripted"
    model_name = OFFLINE_MODEL_NAME

    _INFO_TOOLS = (
        "get_weather",
        "search_flights",
        "search_accommodation",
        "search_attractions",
    )

    def __init__(self, request: TravelRequest) -> None:
        self.request = request
        self._call_counter = 0
        self._info_requests = 0
        self._planner_calls = 0
        self._selected_flight: dict[str, Any] | None = None
        self._selected_hotel: dict[str, Any] | None = None

    def _next_call(self, name: str, arguments: dict[str, Any]) -> LLMToolCall:
        self._call_counter += 1
        return LLMToolCall(
            id=f"offline-call-{self._call_counter}",
            name=name,
            arguments=json.dumps(arguments, ensure_ascii=False),
        )

    @staticmethod
    def _collect_tool_context(
        messages: list[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        call_names: dict[str, str] = {}
        successes: dict[str, dict[str, Any]] = {}
        failures: dict[str, dict[str, Any]] = {}
        for message in messages:
            if message.get("role") == "assistant":
                for tool_call in message.get("tool_calls") or []:
                    call_names[tool_call["id"]] = tool_call["function"]["name"]
            elif message.get("role") == "tool":
                name = call_names.get(message.get("tool_call_id", ""))
                if name is None:
                    continue
                try:
                    payload = json.loads(message.get("content") or "{}")
                except json.JSONDecodeError:
                    continue
                if payload.get("ok"):
                    successes[name] = payload.get("data", {})
                else:
                    failures[name] = payload
        return successes, failures

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        del tools  # The scripted client follows its own deterministic decision tree.
        successes, failures = self._collect_tool_context(messages)

        missing_info = [name for name in self._INFO_TOOLS if name not in successes]
        if missing_info:
            if self._info_requests >= 2:
                failed = ", ".join(missing_info)
                raise LLMError(
                    "The offline scripted client could not obtain required simulated data "
                    f"for: {failed}."
                )
            self._info_requests += 1
            include_budget = self._info_requests == 1
            calls = [
                self._next_call(
                    "get_weather",
                    {
                        "destination": self.request.destination,
                        "start_date": self.request.start_date.isoformat(),
                        "end_date": self.request.end_date.isoformat(),
                    },
                ),
                self._next_call(
                    "search_flights",
                    {
                        "destination": self.request.destination,
                        "departure_city": self.request.departure_city,
                        "departure_date": self.request.start_date.isoformat(),
                        "return_date": self.request.end_date.isoformat(),
                        "currency": self.request.currency,
                        **(
                            {"budget": self.request.budget}
                            if include_budget and "search_flights" not in failures
                            else {}
                        ),
                    },
                ),
                self._next_call(
                    "search_accommodation",
                    {
                        "destination": self.request.destination,
                        "check_in": self.request.start_date.isoformat(),
                        "check_out": self.request.end_date.isoformat(),
                        "currency": self.request.currency,
                        **(
                            {
                                "budget_per_night": round_money(
                                    self.request.budget / self.request.nights
                                )
                            }
                            if include_budget and "search_accommodation" not in failures
                            else {}
                        ),
                    },
                ),
                self._next_call(
                    "search_attractions",
                    {
                        "destination": self.request.destination,
                        "interests": self.request.interests,
                        "dietary_preferences": self.request.dietary_restrictions,
                        "currency": self.request.currency,
                    },
                ),
            ]
            # Retry only the missing information tools.
            calls = [call for call in calls if call.name in missing_info]
            return LLMResponse(
                content=None,
                tool_calls=calls,
                metadata={"provider": self.provider_name, "finish_reason": "tool_calls"},
            )

        attractions_data = successes["search_attractions"]
        flights_data = successes["search_flights"]
        accommodation_data = successes["search_accommodation"]
        weather_data = successes["get_weather"]

        flight_options = flights_data["options"]
        hotel_options = accommodation_data["options"]
        if not flight_options or not hotel_options:
            raise LLMError("Simulated flight or accommodation results were empty.")
        self._selected_flight = min(flight_options, key=lambda option: option["price"])
        self._selected_hotel = min(hotel_options, key=lambda option: option["total_price"])

        planner_data = successes.get("create_daily_itinerary")
        non_food = [
            attraction
            for attraction in attractions_data["attractions"]
            if attraction["category"] != "food"
        ]
        if not non_food:
            raise LLMError("The simulated attraction search returned no schedulable activities.")

        if planner_data is None:
            if self._planner_calls >= 2:
                raise LLMError("The offline scripted planner could not produce feasible days.")
            selected = non_food if self._planner_calls == 0 else self._affordable_attractions(
                non_food, planner_data
            )
            self._planner_calls += 1
            return LLMResponse(
                content=None,
                tool_calls=[
                    self._next_call(
                        "create_daily_itinerary",
                        {
                            "destination": self.request.destination,
                            "start_date": self.request.start_date.isoformat(),
                            "end_date": self.request.end_date.isoformat(),
                            "pace": self.request.pace,
                            "attractions": selected,
                            "currency": self.request.currency,
                        },
                    )
                ],
                metadata={"provider": self.provider_name, "finish_reason": "tool_calls"},
            )

        total = self._total_for(planner_data)
        if total > self.request.budget and self._planner_calls == 1:
            selected = self._affordable_attractions(non_food, planner_data)
            if selected:
                self._planner_calls += 1
                return LLMResponse(
                    content=None,
                    tool_calls=[
                        self._next_call(
                            "create_daily_itinerary",
                            {
                                "destination": self.request.destination,
                                "start_date": self.request.start_date.isoformat(),
                                "end_date": self.request.end_date.isoformat(),
                                "pace": self.request.pace,
                                "attractions": selected,
                                "currency": self.request.currency,
                            },
                        )
                    ],
                    metadata={"provider": self.provider_name, "finish_reason": "tool_calls"},
                )

        plan = self._compose_plan(
            weather_data=weather_data,
            planner_data=planner_data,
            attractions_data=attractions_data,
        )
        return LLMResponse(
            content=json.dumps(plan, ensure_ascii=False),
            metadata={"provider": self.provider_name, "finish_reason": "stop"},
        )

    def _total_for(self, planner_data: dict[str, Any]) -> float:
        assert self._selected_flight is not None
        assert self._selected_hotel is not None
        totals = planner_data["totals"]
        return round_money(
            self._selected_flight["price"]
            + self._selected_hotel["total_price"]
            + totals["food"]
            + totals["activities"]
            + totals["local_transportation"]
        )

    def _affordable_attractions(
        self,
        non_food: list[dict[str, Any]],
        previous_planner_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        assert self._selected_flight is not None
        assert self._selected_hotel is not None
        previous_totals = previous_planner_data["totals"]
        fixed = (
            self._selected_flight["price"]
            + self._selected_hotel["total_price"]
            + previous_totals["food"]
            + previous_totals["local_transportation"]
        )
        activity_budget = max(0.0, self.request.budget - fixed)
        chosen: list[dict[str, Any]] = []
        spent = 0.0
        for attraction in sorted(non_food, key=lambda item: item["price"]):
            if spent + attraction["price"] <= activity_budget + 0.001:
                chosen.append(attraction)
                spent += attraction["price"]
        return chosen

    def _compose_plan(
        self,
        weather_data: dict[str, Any],
        planner_data: dict[str, Any],
        attractions_data: dict[str, Any],
    ) -> dict[str, Any]:
        assert self._selected_flight is not None
        assert self._selected_hotel is not None
        itinerary = planner_data["itinerary"]
        food = round_money(sum(day["daily_food_estimate"] for day in itinerary))
        activities = round_money(
            sum(activity["estimated_cost"] for day in itinerary for activity in day["activities"])
        )
        transport = round_money(sum(day["local_transport_estimate"] for day in itinerary))
        total = round_money(
            self._selected_flight["price"]
            + self._selected_hotel["total_price"]
            + food
            + activities
            + transport
        )
        remaining = round_money(self.request.budget - total)
        respected = total <= self.request.budget

        restaurant_names = [
            attraction["name"]
            for attraction in attractions_data["attractions"]
            if attraction["category"] == "food"
        ]
        recommendations: list[str] = []
        if restaurant_names:
            recommendations.append(
                "Dietary-compatible simulated dining suggestions: "
                + ", ".join(restaurant_names[:3])
                + "."
            )
        if respected:
            recommendations.append(
                f"The simulated total leaves {remaining:.2f} {self.request.currency} "
                "of the requested budget as a contingency."
            )
        else:
            recommendations.append(
                "The simulated total exceeds the requested budget. Reduce the "
                "accommodation category, remove paid activities, or increase the budget."
            )
        recommendations.append(
            "Confirm opening hours, prices, and availability with official providers before "
            "travelling; this plan uses simulated data."
        )

        return {
            "request": self.request.model_dump(mode="json"),
            "summary": (
                f"A simulated {self.request.days}-day, {self.request.nights}-night trip to "
                f"{weather_data['destination']} at a {self.request.pace} pace, shaped around "
                f"{', '.join(self.request.interests)}."
            ),
            "weather": weather_data["days"],
            "selected_flight": self._selected_flight,
            "selected_accommodation": self._selected_hotel,
            "daily_itinerary": itinerary,
            "budget_breakdown": {
                "currency": self.request.currency,
                "flights": self._selected_flight["price"],
                "accommodation": self._selected_hotel["total_price"],
                "food": food,
                "activities": activities,
                "local_transportation": transport,
                "total_estimated_cost": total,
                "budget": self.request.budget,
                "remaining_budget": remaining,
                "budget_respected": respected,
            },
            "recommendations": recommendations,
            "practical_notes": [
                "All data in this offline run is simulated and deterministic; no service is booked.",
                "The day planner assumes 30-minute transfers between activities and respects "
                "simulated opening days and hours.",
                f"Daily meal estimates use a simulated {weather_data['destination']} food allowance.",
            ],
            "data_disclaimer": (
                "All weather, flight, accommodation, attraction, and price information in this "
                "plan is simulated for coursework. It is not verified real-time data and must "
                "not be used for actual booking decisions."
            ),
        }
