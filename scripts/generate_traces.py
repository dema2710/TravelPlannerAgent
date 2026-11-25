"""Generate the two required demonstration traces.

By default this uses the deterministic scripted offline client, because it does
not require an API key. Offline traces are explicitly labelled as simulated.
Pass ``--live`` (with DEEPSEEK_API_KEY configured) to replace them with genuine
DeepSeek tool-calling runs.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from travel_agent.agent import AgentError, TravelAgent
from travel_agent.config import ConfigError, Settings
from travel_agent.display import format_plan
from travel_agent.llm_client import DeepSeekClient, LLMError, ScriptedOfflineLLM
from travel_agent.schemas import TravelRequest
from travel_agent.tools import build_default_registry
from travel_agent.utils.trace_logger import TraceLogger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACE_DIR = PROJECT_ROOT / "traces"

REQUESTS: tuple[tuple[TravelRequest, Path, str], ...] = (
    (
        TravelRequest(
            destination="Paris",
            departure_city="Prague",
            start_date=date(2027, 5, 10),
            end_date=date(2027, 5, 12),
            budget=800.0,
            currency="EUR",
            pace="moderate",
            interests=["architecture", "museums", "history"],
            dietary_restrictions=["vegetarian"],
        ),
        TRACE_DIR / "run_1.jsonl",
        "offline-paris-vegetarian",
    ),
    (
        TravelRequest(
            destination="Prague",
            departure_city="Berlin",
            start_date=date(2027, 9, 3),
            end_date=date(2027, 9, 6),
            budget=480.0,
            currency="EUR",
            pace="relaxed",
            interests=["nature", "food", "history"],
            dietary_restrictions=["vegan"],
        ),
        TRACE_DIR / "run_2.jsonl",
        "offline-prague-vegan",
    ),
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use DeepSeek instead of the offline scripted client.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Optional agent iteration limit.",
    )
    return parser


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (LookupError, ValueError):
                pass


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    args = _build_parser().parse_args(argv)
    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.live and not settings.deepseek_api_key:
        print(
            "DEEPSEEK_API_KEY is required for --live trace generation. "
            "Generate offline traces without --live, or configure the key in .env.",
            file=sys.stderr,
        )
        return 2

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    registry = build_default_registry()
    max_iterations = args.max_iterations or settings.max_iterations
    failures = 0

    for request, trace_path, run_id in REQUESTS:
        mode = "deepseek_live" if args.live else "offline_simulated"
        llm = DeepSeekClient(settings) if args.live else ScriptedOfflineLLM(request)
        trace = TraceLogger(trace_path, run_id=run_id, mode=mode)
        print(f"\nGenerating {trace_path.name} ({mode}) for {request.destination}...")
        try:
            plan = TravelAgent(
                llm=llm,
                registry=registry,
                max_iterations=max_iterations,
                trace=trace,
                progress=lambda message: print(message, flush=True),
            ).run(request)
        except (AgentError, LLMError) as exc:
            failures += 1
            print(f"Failed to generate {trace_path.name}: {exc}", file=sys.stderr)
            continue
        finally:
            trace.close()

        print(format_plan(plan))
        print(f"Trace: {trace_path}")

    if failures:
        print(f"\n{failures} trace(s) failed.", file=sys.stderr)
        return 1
    print(f"\nGenerated {len(REQUESTS)} successful trace(s) in {TRACE_DIR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
