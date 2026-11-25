"""Shared tool error type."""

from __future__ import annotations


class ToolError(RuntimeError):
    """A tool-level error that is safe and useful to show to the LLM."""
