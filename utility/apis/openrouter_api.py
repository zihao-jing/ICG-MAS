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
import json
import os
import sys
import threading
import time
from typing import Optional

try:
    from tqdm import tqdm as _tqdm
    _HAS_TQDM = True
except ImportError:
    _HAS_TQDM = False

# ---------------------------------------------------------------------------
# Intermediate response logging (set via setup_response_log before running)
# ---------------------------------------------------------------------------

_log_path: str | None = None
_log_lock = threading.Lock()


def setup_response_log(path: str) -> None:
    """Direct all batch_request responses to a JSONL file for later analysis."""
    global _log_path
    _log_path = path


def _append_to_log(responses: list) -> None:
    if not _log_path:
        return
    ts = time.time()
    lines = [
        json.dumps({
            "ts": ts,
            "request_id": r.request_id,
            "phase": r.metadata.get("phase"),
            "instance_id": r.metadata.get("instance_id"),
            "agent": r.metadata.get("agent"),
            "model": r.model,
            "success": r.success,
            "content": r.content,
            "usage": r.usage,
            "latency_ms": r.latency_ms,
            "finish_reason": r.metadata.get("finish_reason"),
        }, ensure_ascii=False)
        for r in responses
    ]
    with _log_lock:
        with open(_log_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


_PHASE_LABELS: dict[str, str] = {
    "local":        "local answers",
    "extraction":   "extracting units",
    "scoring":      "scoring units",
    "aggregation":  "aggregating",
    "full_sharing": "full sharing",
    "summary":      "summary exchange",
    "summary_agg":  "summary aggregation",
    "debate":       "debate",
}

from .base import APIRequest, APIResponse, Provider, _Timer
from .errors import APIKeyError, handle_openai_error

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "qwen/qwen3-235b-a22b-2507"
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
    desc: str | None = None,
) -> list[APIResponse]:
    """Send multiple requests concurrently through OpenRouter.

    Responses are returned in the same order as the input list.
    A tqdm progress bar is shown as responses arrive (requires tqdm).

    Args:
        requests:    List of APIRequest objects.
        max_workers: Thread-pool size (default 5).
        desc:        Progress bar label; auto-detected from request metadata if None.

    Returns:
        List of APIResponse objects, one per input request, preserving order.
    """
    if not requests:
        return []

    if desc is None:
        phase = requests[0].metadata.get("phase", "")
        desc = _PHASE_LABELS.get(phase, phase or "requests")

    results: list[Optional[APIResponse]] = [None] * len(requests)
    total = len(requests)
    is_tty = sys.stdout.isatty()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(single_request, req): idx
            for idx, req in enumerate(requests)
        }
        completed_iter = concurrent.futures.as_completed(future_to_idx)

        if _HAS_TQDM and is_tty:
            # Interactive terminal: render a live bar in-place
            completed_iter = _tqdm(
                completed_iter,
                total=total,
                desc=desc,
                unit="req",
                dynamic_ncols=True,
                leave=True,
                file=sys.stdout,
            )
            for future in completed_iter:
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    results[idx] = APIResponse.error_response(requests[idx], PROVIDER, str(exc))
        else:
            # Non-TTY (background job / file redirect): plain-text lines, flushed immediately
            t0 = time.time()
            done = 0
            checkpoints = {max(1, total * p // 10) for p in range(1, 11)}  # 10%, 20%, …, 100%
            for future in completed_iter:
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    results[idx] = APIResponse.error_response(requests[idx], PROVIDER, str(exc))
                done += 1
                if done in checkpoints or done == total:
                    elapsed = time.time() - t0
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (total - done) / rate if rate > 0 else 0
                    print(
                        f"  [{desc}] {done}/{total} ({100*done//total}%)"
                        f"  {rate:.1f} req/s  ETA {eta:.0f}s",
                        flush=True,
                    )

    _append_to_log(results)
    return results  # type: ignore[return-value]
