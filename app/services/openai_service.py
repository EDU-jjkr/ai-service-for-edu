import asyncio
import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, AsyncGenerator, Dict, Literal, Optional

import httpx
from openai import AsyncOpenAI

AIProvider = Literal["openai", "agentrouter"]

_REQUEST_PROVIDER: ContextVar[Optional[str]] = ContextVar("llm_request_provider", default=None)
_REQUEST_MODEL: ContextVar[Optional[str]] = ContextVar("llm_request_model", default=None)

_DEFAULT_PROVIDER = "openai"
_DEFAULT_AGENTROUTER_BASE_URL = "https://agentrouter.org/v1"
_RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_AGENTROUTER_IDENTITY_HEADERS = {
    "HTTP-Referer": "https://kilocode.ai",
    "X-Title": "Kilo Code",
    "User-Agent": "Kilo-Code/2.4.0",
    "X-KILOCODE-EDITORNAME": "Visual Studio Code 2.4.0",
}

_openai_client: Optional[AsyncOpenAI] = None
_agentrouter_client: Optional[httpx.AsyncClient] = None


def _retry_delay(attempt: int) -> float:
    return 0.5 * (2 ** attempt)


def _normalize_provider(value: Optional[str]) -> AIProvider:
    normalized = (value or os.getenv("DEFAULT_AI_PROVIDER", _DEFAULT_PROVIDER)).strip().lower()
    if normalized in {"agent-router", "agent_router"}:
        normalized = "agentrouter"
    if normalized not in {"openai", "agentrouter"}:
        raise ValueError(f"Unsupported AI provider: {value}")
    return normalized  # type: ignore[return-value]


def _resolve_agentrouter_api_key() -> str:
    key = (
        os.getenv("AGENTROUTER_API_KEY")
        or os.getenv("AGENT_ROUTER_API_KEY")
        or os.getenv("AGENT_ROUTER_TOKEN")
    )
    if not key:
        raise RuntimeError(
            "AgentRouter API key is not configured. Set AGENTROUTER_API_KEY or AGENT_ROUTER_TOKEN."
        )
    return key


def _resolve_openai_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OpenAI API key is not configured. Set OPENAI_API_KEY.")
    return key


def _resolve_model(provider: AIProvider, requested_model: Optional[str], *, json_mode: bool) -> str:
    if requested_model:
        return requested_model

    if provider == "agentrouter":
        return os.getenv("AGENTROUTER_MODEL", "claude-opus-4-6")

    if json_mode:
        return os.getenv("OPENAI_JSON_MODEL", "gpt-4o-mini")

    return os.getenv("OPENAI_COMPLETION_MODEL", "gpt-3.5-turbo")


def get_active_ai_settings(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    *,
    json_mode: bool = False,
) -> tuple[AIProvider, str]:
    resolved_provider = _normalize_provider(provider or _REQUEST_PROVIDER.get())
    resolved_model = _resolve_model(resolved_provider, model or _REQUEST_MODEL.get(), json_mode=json_mode)
    return resolved_provider, resolved_model


@contextmanager
def llm_request_context(provider: Optional[str] = None, model: Optional[str] = None):
    provider_token = _REQUEST_PROVIDER.set(provider)
    model_token = _REQUEST_MODEL.set(model)
    try:
        yield
    finally:
        _REQUEST_PROVIDER.reset(provider_token)
        _REQUEST_MODEL.reset(model_token)


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=_resolve_openai_api_key())
    return _openai_client


def _get_agentrouter_client() -> httpx.AsyncClient:
    global _agentrouter_client
    if _agentrouter_client is None:
        _agentrouter_client = httpx.AsyncClient(
            timeout=float(os.getenv("AGENTROUTER_TIMEOUT_SECONDS", "120")),
            headers={
                **_AGENTROUTER_IDENTITY_HEADERS,
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_resolve_agentrouter_api_key()}",
            },
        )
    return _agentrouter_client


def _agentrouter_endpoint() -> str:
    return f"{os.getenv('AGENTROUTER_BASE_URL', _DEFAULT_AGENTROUTER_BASE_URL).rstrip('/')}/chat/completions"


async def _create_openai_chat_completion(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    response_format: Optional[dict[str, str]] = None,
):
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    return await _get_openai_client().chat.completions.create(**payload)


async def _create_openai_chat_stream(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
):
    return await _get_openai_client().chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True,
    )


def _extract_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or payload)
    return str(payload)


async def _post_agentrouter(payload: dict[str, Any]) -> dict[str, Any]:
    client = _get_agentrouter_client()
    last_error: Optional[Exception] = None

    for attempt in range(3):
        if attempt:
            await asyncio.sleep(_retry_delay(attempt - 1))
        try:
            response = await client.post(_agentrouter_endpoint(), json=payload)
        except httpx.TimeoutException as exc:
            last_error = exc
            continue
        except httpx.RequestError as exc:
            raise RuntimeError(f"AgentRouter connection error: {exc}") from exc

        if response.status_code in _RETRY_STATUS_CODES and attempt < 2:
            last_error = RuntimeError(f"AgentRouter temporary error: {response.status_code}")
            continue

        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = response.text
            raise RuntimeError(f"AgentRouter API error ({response.status_code}): {_extract_error_message(body)}")

        return response.json()

    if isinstance(last_error, httpx.TimeoutException):
        raise RuntimeError("AgentRouter request timed out.") from last_error
    raise RuntimeError("AgentRouter request failed after retries.") from last_error


async def _stream_agentrouter(payload: dict[str, Any]) -> AsyncGenerator[str, None]:
    client = _get_agentrouter_client()
    async with client.stream("POST", _agentrouter_endpoint(), json=payload) as response:
        if response.status_code >= 400:
            try:
                body = await response.aread()
                parsed = json.loads(body)
            except Exception:
                parsed = response.reason_phrase or "Unknown AgentRouter error"
            raise RuntimeError(
                f"AgentRouter API error ({response.status_code}): {_extract_error_message(parsed)}"
            )

        async for line in response.aiter_lines():
            clean_line = line.strip()
            if not clean_line.startswith("data:"):
                continue
            data = clean_line[5:].strip()
            if data and data not in {"[DONE]", "null"}:
                yield data


def _extract_json_payload(content: str) -> Dict[str, Any]:
    candidates = [content.strip()]

    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.IGNORECASE | re.DOTALL)
    if fenced_match:
        candidates.append(fenced_match.group(1).strip())

    decoder = json.JSONDecoder()
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        brace_index = candidate.find("{")
        if brace_index == -1:
            continue

        try:
            parsed, _ = decoder.raw_decode(candidate[brace_index:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError("Failed to parse JSON response.")


def _next_agentrouter_json_token_limit(current_limit: int) -> int:
    configured_limit = int(os.getenv("AGENTROUTER_JSON_MAX_TOKENS", "4000"))
    return min(max(current_limit + 400, int(current_limit * 1.5)), configured_limit)


def _build_messages(system_message: str, prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt},
    ]


async def generate_completion(
    prompt: str,
    system_message: str = "You are a helpful AI assistant for education.",
    max_tokens: int = 2000,
    temperature: float = 0.7,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Generate a plain-text completion using the active provider."""
    resolved_provider, resolved_model = get_active_ai_settings(provider, model, json_mode=False)
    messages = _build_messages(system_message, prompt)

    try:
        if resolved_provider == "openai":
            response = await _create_openai_chat_completion(
                model=resolved_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""

        response = await _post_agentrouter(
            {
                "model": resolved_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }
        )
        return response["choices"][0]["message"]["content"]
    except Exception as exc:
        raise Exception(f"{resolved_provider.title()} API error: {exc}") from exc


async def generate_json_completion(
    prompt: str,
    system_message: str = "You are a helpful AI assistant. Always respond with valid JSON.",
    max_tokens: int = 2000,
    temperature: float = 0.7,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a JSON completion while preserving OpenAI's existing json-mode flow."""
    resolved_provider, resolved_model = get_active_ai_settings(provider, model, json_mode=True)
    messages = _build_messages(system_message, prompt)

    try:
        if resolved_provider == "openai":
            response = await _create_openai_chat_completion(
                model=resolved_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
        else:
            attempt_max_tokens = max_tokens
            while True:
                response = await _post_agentrouter(
                    {
                        "model": resolved_model,
                        "messages": messages,
                        "max_tokens": attempt_max_tokens,
                        "temperature": temperature,
                        "stream": False,
                    }
                )
                choice = response["choices"][0]
                content = choice["message"]["content"]

                try:
                    return _extract_json_payload(content)
                except ValueError:
                    if choice.get("finish_reason") != "max_tokens":
                        raise

                    next_limit = _next_agentrouter_json_token_limit(attempt_max_tokens)
                    if next_limit <= attempt_max_tokens:
                        raise ValueError(
                            "Failed to parse JSON response because AgentRouter truncated the output at the max token limit."
                        )
                    attempt_max_tokens = next_limit

        return _extract_json_payload(content)
    except Exception as exc:
        raise Exception(f"{resolved_provider.title()} API error: {exc}") from exc


async def stream_completion(
    prompt: str,
    system_message: str = "You are a helpful AI assistant.",
    max_tokens: int = 2000,
    temperature: float = 0.7,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream completion chunks using the active provider."""
    resolved_provider, resolved_model = get_active_ai_settings(provider, model, json_mode=False)
    messages = _build_messages(system_message, prompt)

    try:
        if resolved_provider == "openai":
            stream = await _create_openai_chat_stream(
                model=resolved_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            return

        async for raw_chunk in _stream_agentrouter(
            {
                "model": resolved_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
        ):
            try:
                payload = json.loads(raw_chunk)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict):
                continue

            content = payload.get("choices", [{}])[0].get("delta", {}).get("content")
            if content:
                yield content
    except Exception as exc:
        yield f"Error: {resolved_provider.title()} API error: {exc}"
