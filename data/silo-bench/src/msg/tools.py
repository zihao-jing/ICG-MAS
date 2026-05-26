"""P2P protocol tool implementations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from src.models import AgentState, ToolCall, ToolResult
from src.utils.persistence import read_json, write_json


def tool_send_message(
    agent_id: int,
    target_id: int,
    content: str,
    round_dir: Path,
    current_round: int,
    state: AgentState,
    num_agents: int,
) -> dict[str, Any]:
    """Send a P2P message to a specific agent."""
    if target_id < 0 or target_id >= num_agents:
        return {"success": False, "message": f"Invalid target_id: {target_id}"}
    if target_id == agent_id:
        return {"success": False, "message": "Cannot send message to yourself"}

    msg_id = str(uuid.uuid4())
    msg_data = {
        "sender_id": agent_id,
        "recipient_id": target_id,
        "content": content,
        "timestamp": current_round,
        "read": False,
    }

    msg_dir = round_dir / "env" / "messages"
    msg_dir.mkdir(parents=True, exist_ok=True)
    write_json(msg_dir / f"{msg_id}.json", msg_data)

    state.messages_sent += 1
    return {"success": True, "message": f"Message sent to agent {target_id}"}


def tool_receive_messages(
    agent_id: int,
    case_dir: Path,
    current_round: int,
    round_dir: Path,
) -> dict[str, Any]:
    """Receive all unread messages addressed to this agent from all previous rounds."""
    messages = []
    rounds_dir = case_dir / "rounds"

    # Scan all previous rounds for unread messages
    for r in range(1, current_round):
        msg_dir = rounds_dir / f"round-{r:06d}" / "env" / "messages"
        if not msg_dir.exists():
            continue
        for msg_file in sorted(msg_dir.glob("*.json")):
            msg = read_json(msg_file)
            if msg["recipient_id"] == agent_id and not msg["read"]:
                messages.append({
                    "from": msg["sender_id"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                })
                # Mark as read
                msg["read"] = True
                write_json(msg_file, msg)

    return {"messages": messages}


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
    """Dispatch and execute a tool call for the P2P protocol."""
    name = tool_call.tool
    params = tool_call.parameters

    try:
        if name == "send_message":
            result = tool_send_message(
                agent_id=agent_id,
                target_id=int(params.get("target_id", -1)),
                content=str(params.get("content", "")),
                round_dir=round_dir,
                current_round=current_round,
                state=state,
                num_agents=num_agents,
            )
        elif name == "receive_messages":
            result = tool_receive_messages(
                agent_id=agent_id,
                case_dir=case_dir,
                current_round=current_round,
                round_dir=round_dir,
            )
            state.messages_received += len(result.get("messages", []))
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
