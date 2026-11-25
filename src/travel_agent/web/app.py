"""FastAPI application serving the travel-planning website and JSON API."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from travel_agent import __version__
from travel_agent.config import Settings
from travel_agent.mock_data import (
    DEFAULT_DEPARTURE_CITY,
    DIETARY_ALIASES,
    INTEREST_ALIASES,
    supported_departure_names,
    supported_destination_names,
)
from travel_agent.utils.money import SUPPORTED_CURRENCIES
from travel_agent.web.schemas import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ItineraryRequest,
    ItineraryResponse,
    WebConfigResponse,
)
from travel_agent.web.service import WebPlanningError, generate_itinerary

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"
PACES = ["relaxed", "moderate", "intensive"]


def _error_response(
    code: str,
    message: str,
    status_code: int,
    details: list[str] | None = None,
    trace_file: str | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or [],
            trace_file=trace_file,
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the web app. Injectable settings make API tests deterministic."""
    resolved_settings = settings or Settings.load()
    if not STATIC_DIR.is_dir():
        raise RuntimeError(f"Frontend static directory is missing: {STATIC_DIR}")

    app = FastAPI(
        title="Travel Planner Agent",
        description="A FastAPI interface around the existing tool-calling travel agent.",
        version=__version__,
    )
    app.state.settings = resolved_settings
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(WebPlanningError)
    async def handle_planning_error(
        request: Request,
        exc: WebPlanningError,
    ) -> JSONResponse:
        del request
        return _error_response(
            code=exc.code,
            message=str(exc),
            status_code=exc.status_code,
            details=exc.details,
            trace_file=exc.trace_file,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request
        details: list[str] = []
        for item in exc.errors()[:10]:
            location = ".".join(str(part) for part in item["loc"])
            details.append(f"{location}: {item['msg']}")
        return _error_response(
            code="validation_error",
            message="The travel request is invalid.",
            status_code=422,
            details=details,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled web API error for %s", request.url.path)
        return _error_response(
            code="internal_error",
            message="The server encountered an unexpected error.",
            status_code=500,
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(live_api_available=bool(resolved_settings.deepseek_api_key))

    @app.get("/api/config", response_model=WebConfigResponse)
    def config() -> WebConfigResponse:
        dietary = sorted(set(DIETARY_ALIASES.values()) - {"omnivore"})
        return WebConfigResponse(
            destinations=supported_destination_names(),
            departure_cities=supported_departure_names(),
            currencies=list(SUPPORTED_CURRENCIES),
            paces=PACES,
            interests=sorted(set(INTEREST_ALIASES.values())),
            dietary_preferences=dietary,
            default_departure_city=DEFAULT_DEPARTURE_CITY,
            live_api_available=bool(resolved_settings.deepseek_api_key),
        )

    @app.post("/api/itineraries", response_model=ItineraryResponse)
    def create_itinerary(payload: ItineraryRequest) -> ItineraryResponse:
        return generate_itinerary(payload, resolved_settings)

    return app


def run() -> None:
    """Launch the local website with Uvicorn."""
    import uvicorn

    uvicorn.run(
        "travel_agent.web.app:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )


app = create_app()
