import os
from openai import AsyncOpenAI
from typing import List, Dict, Any, AsyncGenerator
import json

# Initialize the async client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_completion(
    prompt: str,
    system_message: str = "You are a helpful AI assistant for education.",
    max_tokens: int = 2000,
    temperature: float = 0.7
) -> str:
    """Generate a completion using OpenAI GPT-3.5-Turbo"""
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")

async def generate_json_completion(
    prompt: str,
    system_message: str = "You are a helpful AI assistant. Always respond with valid JSON.",
    max_tokens: int = 2000,
    temperature: float = 0.7
) -> Dict[str, Any]:
    """Generate a JSON completion using OpenAI GPT-3.5-Turbo"""
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError as json_err:
            print(f"JSON Parse Error: {str(json_err)}")
            print(f"Raw Content: {content}")
            raise Exception(f"Failed to parse JSON response: {str(json_err)}")
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")

async def stream_completion(
    prompt: str,
    system_message: str = "You are a helpful AI assistant.",
    max_tokens: int = 2000,
    temperature: float = 0.7
) -> AsyncGenerator[str, None]:
    """Stream completion chunks using OpenAI GPT-3.5-Turbo"""
    try:
        stream = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        print(f"Streaming error: {e}")
        yield f"Error: {str(e)}"
