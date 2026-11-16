"""Single entry point for chat requests; routes Claude Opus 5.5 through the local Claude Code CLI.

Rule (recorded 2026-11-15): Opus 5.5 calls go through `claude -p` (headless print mode), run from an
empty temporary directory with tools disabled and a fixed system prompt file. They do not go through
the paid OpenRouter API. Every other model is passed to the OpenRouter client unchanged.

Scripts import `single_request` from here instead of `utility.apis.openrouter_api`. A request whose
model is an Opus 5.5 id (OpenRouter `anthropic/claude-opus-5.5` or CLI `claude-opus-5-5`) is sent via the
CLI; the request and response shapes are the same as the OpenRouter client's.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

from utility.apis.base import APIRequest, APIResponse, Provider
from utility.apis.openrouter_api import single_request as _openrouter_request

OPUS_IDS = {'anthropic/claude-opus-5.5', 'claude-opus-5-5'}
CLI_MODEL = 'claude-opus-5-5'
TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite Agent Skill '
             'AskUserQuestion ExitPlanMode')
TIMEOUT_S = 900


def _cli_request(request: APIRequest) -> APIResponse:
    t0 = time.monotonic()
    tmp = Path(tempfile.mkdtemp(prefix='opus_cli_'))
    sp = tmp / 'system.txt'
    sp.write_text(request.system_query or '')
    cmd = ['claude', '-p', request.user_query, '--output-format', 'json', '--model', CLI_MODEL,
           '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
           '--disallowedTools', TOOLS_OFF]
    elapsed = lambda: (time.monotonic() - t0) * 1000
    try:
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=TIMEOUT_S)
        obj = json.loads(p.stdout)
    except Exception as exc:  # CLI missing, timeout, or non-JSON output
        return APIResponse.error_response(request, Provider.CLAUDE, f'claude -p failed: {exc}',
                                          latency_ms=elapsed())
    if obj.get('is_error') or p.returncode != 0:
        return APIResponse.error_response(request, Provider.CLAUDE,
                                          f'claude -p error: {obj.get("result") or p.stderr[:300]}',
                                          latency_ms=elapsed())
    u = obj.get('usage') or {}
    pin = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
    pout = u.get('output_tokens', 0)
    metadata = dict(request.metadata)
    metadata['transport'] = 'claude-cli'
    metadata['cli_cost_usd'] = float(obj.get('total_cost_usd') or 0.0)
    return APIResponse(
        content=obj.get('result') or '',
        model=CLI_MODEL,
        provider=Provider.CLAUDE,
        request_id=request.request_id,
        success=True,
        usage={'prompt_tokens': pin, 'completion_tokens': pout, 'total_tokens': pin + pout},
        metadata=metadata,
        latency_ms=elapsed(),
        raw_response=obj,
    )


def single_request(request: APIRequest) -> APIResponse:
    """Opus 5.5 -> `claude -p`; any other model -> OpenRouter (unchanged)."""
    if request.model in OPUS_IDS:
        return _cli_request(request)
    return _openrouter_request(request)
