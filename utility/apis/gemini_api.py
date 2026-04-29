"""
Google Gemini API adapter.

Environment variable required:
    GEMINI_API_KEY  — your Google AI / Gemini API key.

Functions:
    single_request(request)          -> APIResponse
    batch_request(requests, workers) -> list[APIResponse]

Both functions accept the unified APIRequest / APIResponse types defined in
utility.apis.base and raise APIError subclasses on failure (see errors.py).

Note on system prompts:
    Gemini supports a system instruction field via `system_instruction` in the
    GenerativeModel constructor.  The adapter creates a fresh model instance per
    call so that per-request system prompts work correctly.
"""

from __future__ import annotations

import concurrent.futures
import os
from typing import Optional

from .base import APIRequest, APIResponse, Provider, _Timer
from .errors import APIKeyError, handle_google_error

# ---------------------------------------------------------------------------
# Default model
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-2.0-flash"
PROVIDER = Provider.GEMINI


# ---------------------------------------------------------------------------
# SDK import helper
# ---------------------------------------------------------------------------

def _get_genai():
    """Return the google-generativeai module, raising ImportError if absent."""
    try:
        import google.generativeai as genai  # noqa: PLC0415
        return genai
    except ImportError as exc:
        raise ImportError(
            "google-generativeai package is not installed. "
            "Run: pip install google-generativeai"
        ) from exc


def _configure_genai(genai) -> None:
    """Configure the SDK with the API key from the environment (idempotent)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise APIKeyError(
            "GEMINI_API_KEY environment variable is not set.",
            provider=PROVIDER.value,
        )
    genai.configure(api_key=api_key)


# ---------------------------------------------------------------------------
# Single request
# ---------------------------------------------------------------------------

def single_request(request: APIRequest) -> APIResponse:
    """Send a single generate-content request to the Gemini API.

    Args:
        request: Populated APIRequest instance.

    Returns:
        APIResponse with success=True on success, success=False on error.
    """
    genai = _get_genai()
    _configure_genai(genai)

    model_name = request.model or DEFAULT_MODEL

    generation_config = {
        "max_output_tokens": request.max_tokens,
        "temperature": request.temperature,
    }

    with _Timer() as timer:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=request.system_query or None,
                generation_config=generation_config,
            )
            response = model.generate_content(request.user_query)
        except Exception as exc:
            api_err = handle_google_error(exc, PROVIDER.value)
            return APIResponse.error_response(
                request, PROVIDER, str(api_err), latency_ms=timer.elapsed_ms
            )

    # Extract text
    content = ""
    try:
        content = response.text
    except ValueError:
        # response.text raises if the response was blocked
        content = ""

    # Usage metadata (may be None for some response types)
    usage: dict[str, int] = {}
    if response.usage_metadata:
        prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    # Finish reason from the first candidate
    finish_reason = None
    if response.candidates:
        finish_reason = str(response.candidates[0].finish_reason)

    metadata = dict(request.metadata)
    if finish_reason is not None:
        metadata["finish_reason"] = finish_reason

    # Safety ratings
    if response.candidates and response.candidates[0].safety_ratings:
        metadata["safety_ratings"] = [
            {
                "category": str(r.category),
                "probability": str(r.probability),
            }
            for r in response.candidates[0].safety_ratings
        ]

    # Best-effort raw dict
    try:
        raw = type(response).to_dict(response)
    except Exception:
        raw = {}

    return APIResponse(
        content=content,
        model=model_name,
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
    """Send multiple requests concurrently.

    Responses are returned in the same order as the input list.

    Args:
        requests:    List of APIRequest objects.
        max_workers: Thread-pool size (default 5).  Keep this within your
                     Gemini quota's requests-per-minute limit.

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
