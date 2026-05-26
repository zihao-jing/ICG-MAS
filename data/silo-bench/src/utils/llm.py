"""LLM API client with tenacity infinite retry."""

from __future__ import annotations

import httpx
from openai import OpenAI
from tenacity import retry, wait_fixed


@retry(wait=wait_fixed(2))
def call_llm(
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> dict:
    """Call LLM API and return content + token counts.

    Returns:
        {"content": str, "input_tokens": int, "output_tokens": int}

    Retries indefinitely with 2-second intervals on any failure.
    """
    client = OpenAI(base_url=api_base, api_key=api_key, timeout=httpx.Timeout(3600.0))
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    choice = response.choices[0]
    usage = response.usage
    return {
        "content": choice.message.content or "",
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }
