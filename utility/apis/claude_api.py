"""
Anthropic Claude API adapter.

Environment variable required:
    ANTHROPIC_API_KEY  — your Anthropic secret key.

Functions:
    single_request(request)          -> APIResponse
    batch_request(requests, workers) -> list[APIResponse]

Both functions accept the unified APIRequest / APIResponse types defined in
utility.apis.base and raise APIError subclasses on failure (see errors.py).
"""

from __future__ import annotations

import concurrent.futures
import os
from typing import Optional

from .base import APIRequest, APIResponse, Provider, _Timer
from .errors import APIKeyError, handle_anthropic_error

# ---------------------------------------------------------------------------
# Default models
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
PROVIDER = Provider.CLAUDE


# ---------------------------------------------------------------------------
# Client factory (lazy, cached per process)
# ---------------------------------------------------------------------------

_client: Optional[object] = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    try:
        import anthropic  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "anthropic package is not installed. Run: pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise APIKeyError(
            "ANTHROPIC_API_KEY environment variable is not set.",
            provider=PROVIDER.value,
        )

    _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Single request
# ---------------------------------------------------------------------------

def single_request(request: APIRequest) -> APIResponse:
    """Send a single message to the Anthropic Claude API.

    Args:
        request: Populated APIRequest instance.

    Returns:
        APIResponse with success=True on success, success=False on error.
    """
    client = _get_client()

    with _Timer() as timer:
        try:
            response = client.messages.create(
                model=request.model or DEFAULT_MODEL,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=request.system_query,
                messages=[
                    {"role": "user", "content": request.user_query},
                ],
            )
        except Exception as exc:
            api_err = handle_anthropic_error(exc, PROVIDER.value)
            return APIResponse.error_response(
                request, PROVIDER, str(api_err), latency_ms=timer.elapsed_ms
            )

    usage = {}
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        }

    # Extract text from the first content block
    content = ""
    if response.content:
        first_block = response.content[0]
        if hasattr(first_block, "text"):
            content = first_block.text

    metadata = dict(request.metadata)
    metadata["stop_reason"] = response.stop_reason

    return APIResponse(
        content=content,
        model=response.model,
        provider=PROVIDER,
        request_id=request.request_id,
        success=True,
        usage=usage,
        metadata=metadata,
        latency_ms=timer.elapsed_ms,
        raw_response=response.model_dump(),
    )


# ---------------------------------------------------------------------------
# Batch request (concurrent)
# ---------------------------------------------------------------------------

def batch_request(
    requests: list[APIRequest],
    max_workers: int = 5,
) -> list[APIResponse]:
    """Send multiple requests concurrently.

    Responses are returned in the same order as the input list.

    Args:
        requests:    List of APIRequest objects.
        max_workers: Thread-pool size (default 5).  Keep this below your
                     Anthropic tier's requests-per-minute limit.

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
