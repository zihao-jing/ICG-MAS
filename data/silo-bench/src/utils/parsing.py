"""XML tool call parser for LLM output."""

from __future__ import annotations

import json
import re

from src.models import ToolCall

# Regex to extract <tool_call>...</tool_call> blocks
TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
# Regex to extract <tool>name</tool>
TOOL_NAME_RE = re.compile(r"<tool>(.*?)</tool>", re.DOTALL)
# Regex to extract <parameters>...</parameters>
PARAMS_BLOCK_RE = re.compile(r"<parameters>(.*?)</parameters>", re.DOTALL)
# Regex to extract individual <param_name>value</param_name> pairs
PARAM_RE = re.compile(r"<(\w+)>(.*?)</\1>", re.DOTALL)


def _convert_value(value: str) -> int | float | bool | str | list | dict:
    """Smart type conversion: try int, float, bool, JSON (list/dict), else str."""
    stripped = value.strip()
    # bool
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    # int
    try:
        return int(stripped)
    except ValueError:
        pass
    # float
    try:
        return float(stripped)
    except ValueError:
        pass
    # JSON list or dict
    if stripped.startswith(("[", "{")):
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass
    # str (preserve original whitespace-stripped value)
    return stripped


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Parse all <tool_call> blocks from LLM output text.

    Returns a list of ToolCall objects. Gracefully handles malformed blocks
    by skipping them and continuing.
    """
    results = []
    blocks = TOOL_CALL_RE.findall(text)

    for block in blocks:
        # Extract tool name
        name_match = TOOL_NAME_RE.search(block)
        if not name_match:
            continue
        tool_name = name_match.group(1).strip()

        # Extract parameters
        params: dict = {}
        params_match = PARAMS_BLOCK_RE.search(block)
        if params_match:
            params_text = params_match.group(1)
            for param_match in PARAM_RE.finditer(params_text):
                param_name = param_match.group(1)
                param_value = param_match.group(2)
                params[param_name] = _convert_value(param_value)

        results.append(ToolCall(tool=tool_name, parameters=params))

    return results
