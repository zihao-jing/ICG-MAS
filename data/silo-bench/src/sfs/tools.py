"""Shared File System (SFS) protocol tool implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.models import AgentState, ToolCall, ToolResult
from src.utils.persistence import read_json, write_json


def _load_shared_kv(round_dir: Path) -> dict[str, Any]:
    """Load the shared_kv.json for the given round, or return empty dict."""
    kv_path = round_dir / "env" / "shared_kv.json"
    if kv_path.exists():
        return read_json(kv_path)
    return {}


def _save_shared_kv(round_dir: Path, kv: dict[str, Any]) -> None:
    """Save the shared_kv.json for the given round."""
    kv_path = round_dir / "env" / "shared_kv.json"
    kv_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(kv_path, kv)


def tool_list_files(
    prev_round_dir: Path,
    prefix: str | None = None,
) -> dict[str, Any]:
    """List all keys in the shared KV store (reads from previous round)."""
    kv = _load_shared_kv(prev_round_dir)
    files = []
    for key, entry in kv.items():
        if prefix and not key.startswith(prefix):
            continue
        files.append({
            "path": key,
            "modified_by": entry.get("modified_by"),
            "modified_at_round": entry.get("modified_at_round"),
        })
    return {"files": files}


def tool_read_file(
    prev_round_dir: Path,
    path: str,
) -> dict[str, Any]:
    """Read a key's value from the shared KV store (reads from previous round)."""
    kv = _load_shared_kv(prev_round_dir)
    if path not in kv:
        return {"success": False, "content": None, "metadata": {}, "error": f"Key not found: {path}"}

    entry = kv[path]
    return {
        "success": True,
        "content": entry.get("content"),
        "metadata": {
            "modified_by": entry.get("modified_by"),
            "modified_at_round": entry.get("modified_at_round"),
        },
    }


def tool_write_file(
    round_dir: Path,
    agent_id: int,
    current_round: int,
    path: str,
    content: Any,
    state: AgentState,
) -> dict[str, Any]:
    """Write a key-value pair to the shared KV store (writes to current round)."""
    kv = _load_shared_kv(round_dir)
    kv[path] = {
        "content": content,
        "modified_by": agent_id,
        "modified_at_round": current_round,
    }
    _save_shared_kv(round_dir, kv)
    state.files_written += 1
    return {"success": True, "message": f"Written to key: {path}"}


def tool_delete_file(
    round_dir: Path,
    path: str,
) -> dict[str, Any]:
    """Delete a key from the shared KV store (modifies current round)."""
    kv = _load_shared_kv(round_dir)
    if path not in kv:
        return {"success": False, "message": f"Key not found: {path}"}
    del kv[path]
    _save_shared_kv(round_dir, kv)
    return {"success": True, "message": f"Deleted key: {path}"}


def tool_wait() -> dict[str, Any]:
    """Wait for other agents to act."""
    return {"status": "waiting"}


def tool_submit_result(
    agent_id: int,
    answer: Any,
    round_dir: Path,
    current_round: int,
    state: AgentState,
) -> dict[str, Any]:
    """Submit the final answer."""
    if state.submitted:
        return {"status": "already_submitted"}

    submission = {
        "agent_id": agent_id,
        "answer": answer,
        "round": current_round,
    }

    agent_dir = round_dir / f"agent-{agent_id:03d}"
    agent_dir.mkdir(parents=True, exist_ok=True)
    write_json(agent_dir / "submission.json", submission)

    state.submitted = True
    state.submission_round = current_round
    return {"status": "submitted"}


def execute_tool(
    tool_call: ToolCall,
    agent_id: int,
    case_dir: Path,
    round_dir: Path,
    current_round: int,
    state: AgentState,
    num_agents: int,
) -> ToolResult:
    """Dispatch and execute a tool call for the SFS protocol."""
    name = tool_call.tool
    params = tool_call.parameters

    # Determine previous round dir for reads
    rounds_dir = case_dir / "rounds"
    prev_round = max(0, current_round - 1)
    prev_round_dir = rounds_dir / f"round-{prev_round:06d}"

    try:
        if name == "list_files":
            prefix = params.get("prefix")
            if isinstance(prefix, str):
                result = tool_list_files(prev_round_dir, prefix=prefix)
            else:
                result = tool_list_files(prev_round_dir)
            state.files_read += 1
        elif name == "read_file":
            result = tool_read_file(prev_round_dir, path=str(params.get("path", "")))
            state.files_read += 1
        elif name == "write_file":
            result = tool_write_file(
                round_dir=round_dir,
                agent_id=agent_id,
                current_round=current_round,
                path=str(params.get("path", "")),
                content=params.get("content", ""),
                state=state,
            )
        elif name == "delete_file":
            result = tool_delete_file(round_dir, path=str(params.get("path", "")))
        elif name == "wait":
            result = tool_wait()
        elif name == "submit_result":
            result = tool_submit_result(
                agent_id=agent_id,
                answer=params.get("answer"),
                round_dir=round_dir,
                current_round=current_round,
                state=state,
            )
        else:
            return ToolResult(
                tool=name,
                parameters=params,
                result={"error": f"Unknown tool: {name}"},
                success=False,
                error=f"Unknown tool: {name}",
            )

        return ToolResult(tool=name, parameters=params, result=result, success=True)

    except Exception as e:
        return ToolResult(
            tool=name,
            parameters=params,
            result={"error": str(e)},
            success=False,
            error=str(e),
        )
