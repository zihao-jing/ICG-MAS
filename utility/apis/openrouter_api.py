"""
OpenRouter API adapter.

OpenRouter provides a unified endpoint for 200+ models (OpenAI, Anthropic,
Google, Meta, Mistral, …) using the standard OpenAI chat-completions schema.
Models are addressed with a "provider/model" string, e.g.:
    "openai/gpt-4.1-mini"
    "anthropic/claude-3.5-haiku"
    "google/gemini-2.0-flash-001"
    "meta-llama/llama-3.3-70b-instruct"

Docs: https://openrouter.ai/docs/quickstart

Environment variables:
    OPENROUTER_API_KEY      — required
    OPENROUTER_HTTP_REFERER — optional; your site URL (shows on OR leaderboard)
    OPENROUTER_APP_TITLE    — optional; your app name (shows on OR leaderboard)

Functions:
    single_request(request)          -> APIResponse
    batch_request(requests, workers) -> list[APIResponse]
"""

from __future__ import annotations

import concurrent.futures
import os
from typing import Optional

from .base import APIRequest, APIResponse, Provider, _Timer
from .errors import APIKeyError, handle_openai_error

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemma-4-26b-a4b-it"
PROVIDER = Provider.OPENAI          # response structure is OpenAI-compatible;
                                    # callers can inspect .metadata["provider_name"]
                                    # for the actual upstream provider


# ---------------------------------------------------------------------------
# Client factory (lazy, cached per process)
# ---------------------------------------------------------------------------

_client: Optional[object] = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    try:
        import openai  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "openai package is not installed. Run: pip install openai"
        ) from exc

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise APIKeyError(
            "OPENROUTER_API_KEY environment variable is not set.",
            provider="openrouter",
        )

    # Optional attribution headers shown on openrouter.ai leaderboard
    extra_headers: dict[str, str] = {}
    http_referer = os.environ.get("OPENROUTER_HTTP_REFERER", "")
    app_title = os.environ.get("OPENROUTER_APP_TITLE", "")
    if http_referer:
        extra_headers["HTTP-Referer"] = http_referer
    if app_title:
        extra_headers["X-Title"] = app_title

    _client = openai.OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        default_headers=extra_headers or None,
    )
    return _client


# ---------------------------------------------------------------------------
# Single request
# ---------------------------------------------------------------------------

def single_request(request: APIRequest) -> APIResponse:
    """Send a single chat-completion request via OpenRouter.

    The model string should follow OpenRouter's "provider/model" convention,
    e.g. "openai/gpt-4.1-mini", "anthropic/claude-3.5-haiku",
    "google/gemini-2.0-flash-001".  See https://openrouter.ai/models for the
    full list.

    Args:
        request: Populated APIRequest instance.

    Returns:
        APIResponse with success=True on success, success=False on error.
    """
    client = _get_client()

    with _Timer() as timer:
        try:
            response = client.chat.completions.create(
                model=request.model or DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": request.system_query},
                    {"role": "user", "content": request.user_query},
                ],
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
        except Exception as exc:
            api_err = handle_openai_error(exc, "openrouter")
            return APIResponse.error_response(
                request, PROVIDER, str(api_err), latency_ms=timer.elapsed_ms
            )

    usage: dict[str, int] = {}
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    content = response.choices[0].message.content or ""
    model_used = response.model  # OpenRouter echoes the resolved model string

    metadata = dict(request.metadata)
    metadata["finish_reason"] = response.choices[0].finish_reason
    metadata["provider_name"] = "openrouter"

    # OpenRouter may surface the upstream provider in extra fields
    raw = response.model_dump()
    if raw.get("provider"):
        metadata["upstream_provider"] = raw["provider"]

    return APIResponse(
        content=content,
        model=model_used,
        provider=PROVIDER,
        request_id=request.request_id,
        success=True,
        usage=usage,
        metadata=metadata,
        latency_ms=timer.elapsed_ms,
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# Batch request (concurrent)
# ---------------------------------------------------------------------------

def batch_request(
    requests: list[APIRequest],
    max_workers: int = 5,
) -> list[APIResponse]:
    """Send multiple requests concurrently through OpenRouter.

    Responses are returned in the same order as the input list.

    Args:
        requests:    List of APIRequest objects.
        max_workers: Thread-pool size (default 5).

    Returns:
        List of APIResponse objects, one per input request, preserving order.
    """
    if not requests:
        return []

    results: list[Optional[APIResponse]] = [None] * len(requests)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(single_request, req): idx
            for idx, req in enumerate(requests)
        }
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = APIResponse.error_response(
                    requests[idx], PROVIDER, str(exc)
                )

    return results  # type: ignore[return-value]
