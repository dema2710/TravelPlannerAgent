"""Offline tests for the DeepSeek client request/response normalisation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import travel_agent.llm_client as llm_client_module
from travel_agent.config import Settings
from travel_agent.llm_client import DeepSeekClient, LLMError


class _FakeCompletions:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        tool_call = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(name="get_weather", arguments='{"destination": "Paris"}'),
        )
        return SimpleNamespace(
            id="response-1",
            model=kwargs["model"],
            choices=[
                SimpleNamespace(
                    finish_reason="tool_calls",
                    message=SimpleNamespace(content=None, tool_calls=[tool_call]),
                )
            ],
            usage=None,
        )


class _FakeOpenAI:
    last_constructor_kwargs: dict[str, Any] | None = None
    last_completions: _FakeCompletions | None = None

    def __init__(self, **kwargs: Any) -> None:
        type(self).last_constructor_kwargs = kwargs
        completions = _FakeCompletions()
        type(self).last_completions = completions
        self.chat = SimpleNamespace(completions=completions)


def _settings(disable_thinking: bool = True) -> Settings:
    return Settings(
        deepseek_api_key="test-key-not-real",
        model="deepseek-flash",
        disable_thinking=disable_thinking,
    )


def test_deepseek_client_sends_documented_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client_module, "OpenAI", _FakeOpenAI)
    client = DeepSeekClient(_settings())
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]

    response = client.complete([{"role": "user", "content": "Hello"}], tools)

    assert _FakeOpenAI.last_constructor_kwargs is not None
    assert _FakeOpenAI.last_constructor_kwargs["base_url"] == "https://api.deepseek.com"
    assert _FakeOpenAI.last_constructor_kwargs["api_key"] == "test-key-not-real"

    completions = _FakeOpenAI.last_completions
    assert completions is not None
    assert completions.kwargs is not None
    assert completions.kwargs["model"] == "deepseek-flash"
    assert completions.kwargs["tools"] == tools
    assert completions.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert response.tool_calls[0].name == "get_weather"
    assert response.tool_calls[0].id == "call-1"
    assert response.metadata["finish_reason"] == "tool_calls"


def test_deepseek_client_can_leave_thinking_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client_module, "OpenAI", _FakeOpenAI)
    client = DeepSeekClient(_settings(disable_thinking=False))
    client.complete([{"role": "user", "content": "Hello"}], [])
    completions = _FakeOpenAI.last_completions
    assert completions is not None and completions.kwargs is not None
    assert "extra_body" not in completions.kwargs


def test_deepseek_client_requires_api_key() -> None:
    with pytest.raises(LLMError, match="DEEPSEEK_API_KEY"):
        DeepSeekClient(Settings(deepseek_api_key=None))
