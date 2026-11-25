"""Web-to-agent service layer.

This module coordinates the existing TravelAgent, tool registry, LLM clients,
and TraceLogger. It does not duplicate or replace any agent logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from travel_agent.agent import AgentError, TravelAgent
from travel_agent.config import Settings
from travel_agent.llm_client import DeepSeekClient, LLMError, ScriptedOfflineLLM
from travel_agent.tools import build_default_registry
from travel_agent.utils.trace_logger import TraceLogger
from travel_agent.web.schemas import ItineraryRequest, ItineraryResponse

logger = logging.getLogger(__name__)


class WebPlanningError(RuntimeError):
    """A controlled API error with a safe message and optional trace path."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        trace_file: str | None = None,
        details: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.trace_file = trace_file
        self.details = details or []


def _trace_path(settings: Settings, run_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(settings.trace_dir) / f"web_{stamp}_{run_id[:8]}.jsonl"


def generate_itinerary(
    payload: ItineraryRequest,
    settings: Settings,
) -> ItineraryResponse:
    """Run the existing agent for one web request and always close its trace."""
    if payload.mode == "live" and not settings.deepseek_api_key:
        raise WebPlanningError(
            code="live_mode_unavailable",
            message=(
                "DeepSeek live mode is not configured on this server. "
                "Add DEEPSEEK_API_KEY to .env or choose offline mode."
            ),
            status_code=503,
        )

    run_id = uuid4().hex
    trace_path = _trace_path(settings, run_id)
    trace_file = trace_path.as_posix()
    trace_mode = "web_offline_simulated" if payload.mode == "offline" else "web_deepseek_live"

    try:
        trace = TraceLogger(trace_path, run_id=run_id, mode=trace_mode)
    except OSError as exc:
        logger.exception("Could not create trace file for web request")
        raise WebPlanningError(
            code="trace_write_failed",
            message="The server could not create a trace file for this request.",
            status_code=500,
        ) from exc

    try:
        if payload.mode == "live":
            try:
                llm = DeepSeekClient(settings)
            except LLMError as exc:
                raise WebPlanningError(
                    code="live_client_error",
                    message=str(exc),
                    status_code=503,
                    trace_file=trace_file,
                ) from exc
        else:
            llm = ScriptedOfflineLLM(payload.request)

        agent = TravelAgent(
            llm=llm,
            registry=build_default_registry(),
            max_iterations=settings.max_iterations,
            trace=trace,
        )
        try:
            plan = agent.run(payload.request)
        except AgentError as exc:
            raise WebPlanningError(
                code="planning_failed",
                message=str(exc),
                status_code=500,
                trace_file=trace_file,
            ) from exc
        except Exception as exc:  # Keep internal details out of the HTTP response.
            logger.exception("Unexpected web planning failure")
            raise WebPlanningError(
                code="internal_error",
                message="The planning agent failed unexpectedly.",
                status_code=500,
                trace_file=trace_file,
            ) from exc

        return ItineraryResponse(
            plan=plan,
            trace_file=trace_file,
            run_id=run_id,
            mode=payload.mode,
            provider=llm.provider_name,
            model=llm.model_name,
        )
    finally:
        trace.close()
