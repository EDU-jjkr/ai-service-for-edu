import os
import json
from openai import AsyncOpenAI
from typing import Dict, Any, AsyncGenerator

# Initialize the async client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DEFAULT_MODEL = os.getenv("OPENAI_JSON_MODEL", "gpt-5.6-luna")
DEFAULT_COMPLETION_MODEL = os.getenv("OPENAI_COMPLETION_MODEL", "gpt-5.6-luna")
DEFAULT_MAX_TOKENS = int(os.getenv("MAX_TOKENS", "32768"))

# gpt-5.6-luna only supports the default temperature (1).
# We keep the parameter in function signatures for API compatibility
# but never forward it to the OpenAI call.


async def generate_completion(
    prompt: str,
    system_message: str = "You are a helpful AI assistant for education.",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 1,  # ignored — model only supports default
    model: str = None,
) -> str:
    """Generate a completion using gpt-5.6-luna."""
    selected_model = model or DEFAULT_COMPLETION_MODEL
    try:
        response = await client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")


import re

def _clean_json_string(content: str) -> str:
    if not content:
        return ""
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def _extract_json_payload(content: str) -> str:
    cleaned = _clean_json_string(content)
    if not cleaned:
        return ""
    try:
        json.loads(cleaned)
        return cleaned
    except json.JSONDecodeError:
        pass
    
    match = re.search(r'(\{[\s\S]*\})', cleaned)
    if match:
        possible = match.group(1)
        try:
            json.loads(possible)
            return possible
        except json.JSONDecodeError:
            pass

    return cleaned


async def generate_json_completion(
    prompt: str,
    system_message: str = "You are a helpful AI assistant. Always respond with valid JSON.",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 1,  # ignored — model only supports default
    model: str = None,
) -> Dict[str, Any]:
    """Generate a JSON completion using gpt-5.6-luna."""
    selected_model = model or DEFAULT_MODEL
    try:
        response = await client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        choice = response.choices[0] if response.choices else None
        content = choice.message.content if choice and choice.message else ""
        finish_reason = choice.finish_reason if choice else "unknown"

        cleaned_content = _extract_json_payload(content or "")

        if not cleaned_content:
            print(f"Empty OpenAI Content! finish_reason={finish_reason}, raw_content={repr(content)}")
            raise Exception(f"OpenAI returned empty response (finish_reason: {finish_reason})")

        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError as json_err:
            print(f"JSON Parse Error: {str(json_err)}")
            print(f"Raw Content: {content}")
            print(f"Cleaned Content: {cleaned_content}")
            raise Exception(f"Failed to parse JSON response: {str(json_err)}")
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")


async def stream_completion(
    prompt: str,
    system_message: str = "You are a helpful AI assistant.",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 1,  # ignored — model only supports default
    model: str = None,
) -> AsyncGenerator[str, None]:
    """Stream completion chunks using gpt-5.6-luna."""
    selected_model = model or DEFAULT_COMPLETION_MODEL
    try:
        stream = await client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        print(f"Streaming error: {e}")
        yield f"Error: {str(e)}"
