"""Protocol-specific system prompt generation with XML tool documentation."""

from __future__ import annotations

MSG_TOOLS_DOC = """
## Available Tools

You MUST use the following XML format for tool calls:

```xml
<tool_call>
  <tool>tool_name</tool>
  <parameters>
    <param1>value1</param1>
  </parameters>
</tool_call>
```

### Tools:

1. **send_message** - Send a message to a specific agent
   Parameters:
   - target_id (int): The ID of the recipient agent
   - content (str): The message content
   Returns: {"success": true/false, "message": "..."}
   Example:
   <tool_call>
     <tool>send_message</tool>
     <parameters>
       <target_id>2</target_id>
       <content>My local maximum is 914</content>
     </parameters>
   </tool_call>

2. **receive_messages** - Receive all new messages sent to you
   Parameters: none
   Returns: {"messages": [{"from": int, "content": str, "timestamp": int}, ...]}
   Example:
   <tool_call>
     <tool>receive_messages</tool>
     <parameters>
     </parameters>
   </tool_call>

3. **wait** - Wait for other agents to act (ends your turn for this round)
   Parameters: none
   Returns: {"status": "waiting"}
   Example:
   <tool_call>
     <tool>wait</tool>
     <parameters>
     </parameters>
   </tool_call>

4. **submit_result** - Submit your final answer
   Parameters:
   - answer (any): Your final answer
   Returns: {"status": "submitted"}
   Example:
   <tool_call>
     <tool>submit_result</tool>
     <parameters>
       <answer>1000</answer>
     </parameters>
   </tool_call>

**IMPORTANT RULES:**
- Messages sent this round will be received by others NEXT round
- You can send multiple messages and then wait, or receive and then send
- **wait** and **submit_result** are ROUND-ENDING tools: once you call either one, your turn ends immediately and no further tool calls will be executed this round
- So place send_message / receive_messages BEFORE wait in your tool call sequence
- Once you submit, you cannot perform any more actions
- ALL agents must submit their final answer
- Do NOT hallucinate tool results — the system will provide results after your tool calls
- You may call multiple tools in a single turn, but remember wait/submit_result ends the turn
"""

BROADCAST_TOOLS_DOC = """
## Available Tools

You MUST use the following XML format for tool calls:

```xml
<tool_call>
  <tool>tool_name</tool>
  <parameters>
    <param1>value1</param1>
  </parameters>
</tool_call>
```

### Tools:

1. **broadcast_message** - Broadcast a message to ALL other agents
   Parameters:
   - content (str): The message content
   Returns: {"success": true/false, "message": "..."}
   Example:
   <tool_call>
     <tool>broadcast_message</tool>
     <parameters>
       <content>My local maximum is 914</content>
     </parameters>
   </tool_call>

2. **receive_messages** - Receive all new broadcast messages
   Parameters: none
   Returns: {"messages": [{"from": int, "content": str, "timestamp": int}, ...]}
   Example:
   <tool_call>
     <tool>receive_messages</tool>
     <parameters>
     </parameters>
   </tool_call>

3. **list_agents** - Get the list of all agent IDs in the system
   Parameters: none
   Returns: {"agent_ids": [0, 1, 2, ...], "total": int}
   Example:
   <tool_call>
     <tool>list_agents</tool>
     <parameters>
     </parameters>
   </tool_call>

4. **wait** - Wait for other agents to act (ends your turn for this round)
   Parameters: none
   Returns: {"status": "waiting"}
   Example:
   <tool_call>
     <tool>wait</tool>
     <parameters>
     </parameters>
   </tool_call>

5. **submit_result** - Submit your final answer
   Parameters:
   - answer (any): Your final answer
   Returns: {"status": "submitted"}
   Example:
   <tool_call>
     <tool>submit_result</tool>
     <parameters>
       <answer>1000</answer>
     </parameters>
   </tool_call>

**IMPORTANT RULES:**
- Broadcasts sent this round will be received by others NEXT round
- You can broadcast, receive, and then decide to wait or submit
- **wait** and **submit_result** are ROUND-ENDING tools: once you call either one, your turn ends immediately and no further tool calls will be executed this round
- So place broadcast_message / receive_messages / list_agents BEFORE wait in your tool call sequence
- Once you submit, you cannot perform any more actions
- ALL agents must submit their final answer
- Do NOT hallucinate tool results — the system will provide results after your tool calls
- You may call multiple tools in a single turn, but remember wait/submit_result ends the turn
"""

SFS_TOOLS_DOC = """
## Available Tools

You MUST use the following XML format for tool calls:

```xml
<tool_call>
  <tool>tool_name</tool>
  <parameters>
    <param1>value1</param1>
  </parameters>
</tool_call>
```

### Tools:

1. **list_files** - List all keys in the shared file system (optionally filtered by prefix)
   Parameters:
   - prefix (str, optional): Filter keys by prefix
   Returns: {"files": [{"path": str, "modified_by": int, "modified_at_round": int}, ...]}
   Example:
   <tool_call>
     <tool>list_files</tool>
     <parameters>
       <prefix>agent_</prefix>
     </parameters>
   </tool_call>

2. **read_file** - Read the value of a key from the shared file system
   Parameters:
   - path (str): The key to read
   Returns: {"success": true/false, "content": any, "metadata": {"modified_by": int, "modified_at_round": int}}
   Example:
   <tool_call>
     <tool>read_file</tool>
     <parameters>
       <path>agent_0_data</path>
     </parameters>
   </tool_call>

3. **write_file** - Write a value to a key in the shared file system
   Parameters:
   - path (str): The key to write
   - content (any): The value to store
   Returns: {"success": true/false, "message": "..."}
   Example:
   <tool_call>
     <tool>write_file</tool>
     <parameters>
       <path>agent_0_data</path>
       <content>My local maximum is 914</content>
     </parameters>
   </tool_call>

4. **delete_file** - Delete a key from the shared file system
   Parameters:
   - path (str): The key to delete
   Returns: {"success": true/false, "message": "..."}
   Example:
   <tool_call>
     <tool>delete_file</tool>
     <parameters>
       <path>temp_data</path>
     </parameters>
   </tool_call>

5. **wait** - Wait for other agents to act (ends your turn for this round)
   Parameters: none
   Returns: {"status": "waiting"}
   Example:
   <tool_call>
     <tool>wait</tool>
     <parameters>
     </parameters>
   </tool_call>

6. **submit_result** - Submit your final answer
   Parameters:
   - answer (any): Your final answer
   Returns: {"status": "submitted"}
   Example:
   <tool_call>
     <tool>submit_result</tool>
     <parameters>
       <answer>1000</answer>
     </parameters>
   </tool_call>

**IMPORTANT RULES:**
- Files written this round will be readable by others NEXT round
- read_file and list_files show data from the PREVIOUS round
- **wait** and **submit_result** are ROUND-ENDING tools: once you call either one, your turn ends immediately and no further tool calls will be executed this round
- So place list_files / read_file / write_file / delete_file BEFORE wait in your tool call sequence
- Once you submit, you cannot perform any more actions
- ALL agents must submit their final answer
- Do NOT hallucinate tool results — the system will provide results after your tool calls
- You may call multiple tools in a single turn, but remember wait/submit_result ends the turn
"""


def generate_system_prompt(protocol: str, agent_id: int, num_agents: int) -> str:
    """Generate a protocol-specific system prompt for an agent.

    Args:
        protocol: "msg", "broadcast", or "sfs"
        agent_id: This agent's ID
        num_agents: Total number of agents

    Returns:
        Complete system prompt string with tool documentation.
    """
    max_id = num_agents - 1

    base = f"""You are a member of a multi-agent system composed of {num_agents} intelligent agents.

**Your Identity:**
- Your unique agent ID is: {agent_id}
- Total agents in the system: {num_agents} (IDs from 0 to {max_id})

**Communication Paradigm:**
You operate in a collaborative setting. You must use the provided tools to communicate with other agents and submit your answer.

**Your Objective:**
Work collaboratively with other agents to solve the given task efficiently. You should:
- Analyze the task structure and data dependencies
- Determine the optimal communication strategy
- Minimize redundant communications
- Reach consensus on the correct answer

**CRITICAL: Every agent must submit the final answer!**
- Do NOT assume only a "leader" should submit
- ALL agents (including you) must call submit_result() with the correct answer
- Coordinate with other agents to ensure everyone has the correct answer before submitting
"""

    if protocol == "msg":
        tools_doc = MSG_TOOLS_DOC
    elif protocol == "broadcast":
        tools_doc = BROADCAST_TOOLS_DOC
    elif protocol == "sfs":
        tools_doc = SFS_TOOLS_DOC
    else:
        raise ValueError(f"Unknown protocol: {protocol}")

    return base + tools_doc
