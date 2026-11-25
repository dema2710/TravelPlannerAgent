"""Tool registry with argument validation and structured error handling."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from travel_agent.tools.errors import ToolError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolDefinition:
    """Metadata and handler for one tool exposed to the LLM."""

    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[..., dict[str, Any]]

    def openai_schema(self) -> dict[str, Any]:
        """Return the OpenAI-compatible function tool definition."""
        parameters = self.input_model.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


@dataclass(frozen=True)
class ToolExecution:
    """Outcome of executing a tool call."""

    tool_name: str
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    error_type: str | None = None
    content: str = field(default="")

    @classmethod
    def success(cls, tool_name: str, data: dict[str, Any]) -> "ToolExecution":
        content = json.dumps(
            {"ok": True, "tool": tool_name, "data": data},
            ensure_ascii=False,
        )
        return cls(tool_name=tool_name, ok=True, data=data, content=content)

    @classmethod
    def failure(
        cls,
        tool_name: str,
        error: str,
        error_type: str,
    ) -> "ToolExecution":
        content = json.dumps(
            {"ok": False, "tool": tool_name, "error": error, "error_type": error_type},
            ensure_ascii=False,
        )
        return cls(
            tool_name=tool_name,
            ok=False,
            error=error,
            error_type=error_type,
            content=content,
        )


class ToolRegistry:
    """An explicit mapping from tool names to validated Python functions."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' is already registered.")
        self._tools[definition.name] = definition

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def openai_tools(self) -> list[dict[str, Any]]:
        return [definition.openai_schema() for definition in self._tools.values()]

    def execute(self, name: str, arguments: str | dict[str, Any] | None) -> ToolExecution:
        """Validate and execute one tool call without raising to the agent."""
        definition = self._tools.get(name)
        if definition is None:
            available = ", ".join(self.tool_names) or "(none)"
            return ToolExecution.failure(
                name,
                f"Unknown tool '{name}'. Available tools: {available}.",
                "unknown_tool",
            )

        if arguments is None or (isinstance(arguments, str) and not arguments.strip()):
            raw_arguments: Any = {}
        elif isinstance(arguments, str):
            try:
                raw_arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                return ToolExecution.failure(
                    name,
                    f"Tool arguments are not valid JSON: {exc.msg}.",
                    "invalid_arguments",
                )
        else:
            raw_arguments = arguments

        if not isinstance(raw_arguments, dict):
            return ToolExecution.failure(
                name,
                "Tool arguments must be a JSON object.",
                "invalid_arguments",
            )

        try:
            validated = definition.input_model.model_validate(raw_arguments)
        except ValidationError as exc:
            details = []
            for item in exc.errors()[:8]:
                location = ".".join(str(part) for part in item["loc"]) or "arguments"
                details.append(f"{location}: {item['msg']}")
            return ToolExecution.failure(
                name,
                "Invalid tool arguments. " + "; ".join(details),
                "invalid_arguments",
            )

        try:
            result = definition.handler(**validated.model_dump())
        except ToolError as exc:
            return ToolExecution.failure(name, str(exc), "tool_error")
        except Exception as exc:  # Defensive boundary around tool execution.
            logger.exception("Unexpected error while executing tool '%s'", name)
            return ToolExecution.failure(
                name,
                f"The tool failed unexpectedly ({type(exc).__name__}): {exc}",
                "tool_exception",
            )

        if not isinstance(result, dict):
            return ToolExecution.failure(
                name,
                "The tool returned an unsupported response type.",
                "invalid_tool_response",
            )
        return ToolExecution.success(name, result)
