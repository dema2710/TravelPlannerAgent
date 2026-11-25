"""Command-line interface for the AI Travel Planner Agent."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from pydantic import ValidationError

from travel_agent.agent import AgentError, TravelAgent
from travel_agent.config import ConfigError, Settings
from travel_agent.display import format_plan
from travel_agent.llm_client import DeepSeekClient, LLMError, ScriptedOfflineLLM
from travel_agent.mock_data import (
    DEFAULT_DEPARTURE_CITY,
    resolve_city,
    resolve_departure_city,
    supported_departure_names,
    supported_destination_names,
)
from travel_agent.schemas import Pace, TravelRequest
from travel_agent.tools import build_default_registry
from travel_agent.utils.money import SUPPORTED_CURRENCIES
from travel_agent.utils.trace_logger import TraceLogger


def _configure_console() -> None:
    """Use UTF-8 where possible so non-ASCII mock place names render safely."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (LookupError, ValueError):
                pass


def _split_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]


def _prompt_nonempty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Please enter a value.")


def _prompt_date(prompt: str) -> date:
    while True:
        raw = input(prompt).strip()
        try:
            return date.fromisoformat(raw)
        except ValueError:
            print("Use ISO format YYYY-MM-DD (for example 2027-05-10).")


def _prompt_budget() -> float:
    while True:
        raw = input("Total budget (positive number, one traveller): ").strip()
        try:
            budget = float(raw)
        except ValueError:
            print("Budget must be a number.")
            continue
        if budget <= 0:
            print("Budget must be greater than zero.")
            continue
        return round(budget, 2)


def _prompt_currency() -> str:
    supported = ", ".join(SUPPORTED_CURRENCIES)
    while True:
        raw = input(f"Currency [{supported}] (default EUR): ").strip().upper() or "EUR"
        if raw in SUPPORTED_CURRENCIES:
            return raw
        print(f"Unsupported currency. Choose one of: {supported}.")


def _prompt_pace() -> Pace:
    while True:
        raw = input("Preferred pace - relaxed / moderate / intensive [moderate]: ").strip().lower()
        if not raw:
            return "moderate"
        if raw in {"relaxed", "moderate", "intensive"}:
            return raw  # type: ignore[return-value]
        print("Choose relaxed, moderate, or intensive.")


def collect_interactive_request() -> TravelRequest:
    """Interactively collect and validate a travel request."""
    destinations = ", ".join(supported_destination_names())
    departure_cities = ", ".join(supported_departure_names())
    print(f"Supported simulated destinations: {destinations}")
    print(f"Supported departure cities: {departure_cities}")

    while True:
        raw_destination = _prompt_nonempty("Destination: ")
        city = resolve_city(raw_destination)
        if city is not None:
            break
        print(f"Unsupported destination. Choose from: {destinations}.")

    while True:
        raw_departure = (
            input(f"Departure city [{DEFAULT_DEPARTURE_CITY}]: ").strip()
            or DEFAULT_DEPARTURE_CITY
        )
        departure = resolve_departure_city(raw_departure)
        if departure is None:
            print(f"Unsupported departure city. Choose from: {departure_cities}.")
            continue
        if departure.key == city.key:
            print("Departure city must differ from the destination.")
            continue
        break

    while True:
        start = _prompt_date("Departure date (YYYY-MM-DD): ")
        end = _prompt_date("Return date (YYYY-MM-DD): ")
        if end <= start:
            print("Return date must be after the departure date.")
            continue
        break

    budget = _prompt_budget()
    currency = _prompt_currency()
    pace = _prompt_pace()

    while True:
        interests = _split_list(_prompt_nonempty("Interests (comma-separated): "))
        if interests:
            break
        print("Enter at least one interest.")

    dietary = _split_list(
        input(
            "Dietary restrictions (comma-separated, or press Enter for none): "
        )
    )

    try:
        return TravelRequest(
            destination=city.name,
            departure_city=departure.name,
            start_date=start,
            end_date=end,
            budget=budget,
            currency=currency,
            pace=pace,
            interests=interests,
            dietary_restrictions=dietary,
        )
    except ValidationError as exc:
        first_error = exc.errors(include_url=False)[0]
        raise ValueError(first_error["msg"]) from exc


def load_request_file(path: Path) -> TravelRequest:
    """Load a travel request from a JSON file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read request file '{path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Request file '{path}' is not valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc
    if not isinstance(raw, dict):
        raise ValueError("The request file must contain a JSON object.")
    try:
        request = TravelRequest.model_validate(raw)
    except ValidationError as exc:
        details = []
        for error in exc.errors(include_url=False)[:6]:
            location = ".".join(str(part) for part in error["loc"]) or "request"
            details.append(f"{location}: {error['msg']}")
        raise ValueError("Invalid travel request: " + "; ".join(details)) from exc

    city = resolve_city(request.destination)
    if city is None:
        raise ValueError(
            f"Unsupported destination '{request.destination}'. Supported destinations: "
            + ", ".join(supported_destination_names())
            + "."
        )
    if city.name != request.destination:
        request = request.model_copy(update={"destination": city.name})
    return request


def _build_trace_path(settings: Settings, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return settings.trace_dir / f"run_{stamp}_{uuid4().hex[:6]}.jsonl"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AI Travel Planner Agent with an explicit DeepSeek tool-calling loop."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the deterministic scripted offline model instead of DeepSeek.",
    )
    parser.add_argument(
        "--request",
        type=Path,
        metavar="FILE",
        help="Load the travel request from a JSON file instead of interactive prompts.",
    )
    parser.add_argument(
        "--trace",
        type=Path,
        metavar="FILE",
        help="Write the JSONL trace to this path (default: traces/run_<timestamp>.jsonl).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        metavar="N",
        help="Override AGENT_MAX_ITERATIONS for this run.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    _configure_console()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        request = (
            load_request_file(args.request)
            if args.request is not None
            else collect_interactive_request()
        )
    except (ValueError, EOFError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            print("\nCancelled.")
            return 130
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    max_iterations = args.max_iterations or settings.max_iterations
    if max_iterations < 1:
        print("--max-iterations must be at least 1.", file=sys.stderr)
        return 2

    if not args.offline and not settings.deepseek_api_key:
        print(
            "DEEPSEEK_API_KEY is not configured. Add it to .env, or run with --offline.",
            file=sys.stderr,
        )
        return 2

    trace_path = _build_trace_path(settings, args.trace)
    run_id = uuid4().hex
    mode = "offline_simulated" if args.offline else "deepseek_live"
    try:
        trace = TraceLogger(trace_path, run_id=run_id, mode=mode)
    except OSError as exc:
        print(f"Could not create trace file '{trace_path}': {exc}", file=sys.stderr)
        return 2

    registry = build_default_registry()
    try:
        if args.offline:
            llm = ScriptedOfflineLLM(request)
            print("[Mode] Offline deterministic simulation - no DeepSeek API call will be made.")
        else:
            llm = DeepSeekClient(settings)
            print(
                f"[Mode] DeepSeek live API | model={settings.model} | "
                f"base_url={settings.base_url}"
            )

        print(f"[Mode] Trace: {trace_path}")
        print(
            f"[Request] {request.destination} from {request.departure_city}, "
            f"{request.start_date} to {request.end_date}, "
            f"{request.budget:.2f} {request.currency}, {request.pace} pace"
        )
        print("")

        agent = TravelAgent(
            llm=llm,
            registry=registry,
            max_iterations=max_iterations,
            trace=trace,
            progress=lambda message: print(message, flush=True),
        )
        plan = agent.run(request)
        print("")
        print(format_plan(plan))
        print("")
        print(f"Trace written to: {trace.path}")
        return 0
    except (AgentError, LLMError) as exc:
        print("", file=sys.stderr)
        print(f"Planning failed: {exc}", file=sys.stderr)
        print(f"Trace written to: {trace.path}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:  # Final CLI boundary: do not dump a traceback to the user.
        logging.getLogger(__name__).exception("Unexpected CLI failure")
        print(f"Unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"Trace written to: {trace.path}", file=sys.stderr)
        return 1
    finally:
        trace.close()


if __name__ == "__main__":
    raise SystemExit(main())
