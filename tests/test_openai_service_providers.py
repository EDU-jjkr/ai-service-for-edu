import asyncio
import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from app.services.openai_service import (
    _extract_json_payload,
    generate_json_completion,
    get_active_ai_settings,
    llm_request_context,
)


def test_extract_json_payload_accepts_markdown_fences():
    payload = _extract_json_payload(
        """```json
        {"status": "ok", "count": 2}
        ```"""
    )

    assert payload == {"status": "ok", "count": 2}


def test_llm_request_context_overrides_default_provider(monkeypatch):
    monkeypatch.setenv("DEFAULT_AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_JSON_MODEL", "gpt-4o-mini")

    provider, model = get_active_ai_settings(json_mode=True)
    assert provider == "openai"
    assert model == "gpt-4o-mini"

    with llm_request_context("agentrouter", "claude-opus-4-6"):
        provider, model = get_active_ai_settings(json_mode=True)
        assert provider == "agentrouter"
        assert model == "claude-opus-4-6"


def test_generate_json_completion_retries_agentrouter_when_json_is_truncated(monkeypatch):
    monkeypatch.setenv("DEFAULT_AI_PROVIDER", "agentrouter")
    monkeypatch.setenv("AGENTROUTER_MODEL", "claude-opus-4-6")
    monkeypatch.setenv("AGENTROUTER_JSON_MAX_TOKENS", "4000")

    truncated = {
        "choices": [
            {
                "finish_reason": "max_tokens",
                "message": {"content": '{"slides": [{"title": "Intro"}'},
            }
        ]
    }
    completed = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": '{"slides": [{"title": "Intro"}]}'},
            }
        ]
    }

    with patch("app.services.openai_service._post_agentrouter", new=AsyncMock(side_effect=[truncated, completed])) as mock_post:
        payload = asyncio.run(
            generate_json_completion(
                prompt="Return slides.",
                system_message="Return valid JSON.",
                max_tokens=1200,
            )
        )

    assert payload == {"slides": [{"title": "Intro"}]}
    assert mock_post.await_count == 2
    first_payload = mock_post.await_args_list[0].args[0]
    second_payload = mock_post.await_args_list[1].args[0]
    assert first_payload["max_tokens"] == 1200
    assert second_payload["max_tokens"] > first_payload["max_tokens"]
