#!/usr/bin/env python3
"""Mock multi-agent MCP server: delegate_task, reasoning_step, memory_store, memory_retrieve.

Tests agent-specific span types (agent_turn, agent_handoff, reasoning_step).
"""
import json
import sys
import time

TOOLS = [
    {"name": "delegate_task", "description": "Delegate a task to a sub-agent", "inputSchema": {"type": "object", "properties": {"agent_name": {"type": "string"}, "task": {"type": "string"}, "context": {"type": "string"}}, "required": ["agent_name", "task"]}},
    {"name": "reasoning_step", "description": "Execute a chain-of-thought reasoning step", "inputSchema": {"type": "object", "properties": {"step": {"type": "string"}, "premises": {"type": "array", "items": {"type": "string"}}}, "required": ["step"]}},
    {"name": "memory_store", "description": "Store a key-value pair in agent memory", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}, "ttl_seconds": {"type": "integer"}}, "required": ["key", "value"]}},
    {"name": "memory_retrieve", "description": "Retrieve a value from agent memory", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
]

MEMORY = {}

FAKE_AGENTS = {
    "researcher": "I found 3 relevant papers on the topic.",
    "coder": "Implementation complete. 42 lines of Python added.",
    "reviewer": "Code review passed with 2 minor suggestions.",
}


def respond(msg_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\n")
    sys.stdout.flush()


def handle_tool_call(msg_id, name, args):
    if name == "delegate_task":
        agent = args.get("agent_name", "researcher")
        result = FAKE_AGENTS.get(agent, f"Agent '{agent}' completed the task.")
        respond(msg_id, {"content": [{"type": "text", "text": json.dumps({
            "agent": agent,
            "task": args.get("task", ""),
            "status": "completed",
            "result": result,
            "tokens_used": 1250,
        })}]})
    elif name == "reasoning_step":
        premises = args.get("premises", [])
        respond(msg_id, {"content": [{"type": "text", "text": json.dumps({
            "step": args.get("step", ""),
            "premises_count": len(premises),
            "conclusion": f"Based on {len(premises)} premises, the conclusion follows logically.",
            "confidence": 0.87,
        })}]})
    elif name == "memory_store":
        key = args.get("key", "")
        MEMORY[key] = args.get("value", "")
        respond(msg_id, {"content": [{"type": "text", "text": json.dumps({"stored": key, "ttl": args.get("ttl_seconds", 3600)})}]})
    elif name == "memory_retrieve":
        key = args.get("key", "")
        val = MEMORY.get(key, None)
        respond(msg_id, {"content": [{"type": "text", "text": json.dumps({"key": key, "value": val, "found": val is not None})}]})
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Unknown tool: {name}"}}) + "\n")
        sys.stdout.flush()


def main():
    sys.stderr.write("mock-agent-mcp: started\n")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            respond(msg_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "mock-agent-mcp", "version": "1.0.0"}})
        elif method == "tools/list":
            respond(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            handle_tool_call(msg_id, params.get("name", ""), params.get("arguments", {}))
        elif method == "ping":
            respond(msg_id, {})
        else:
            respond(msg_id, {})


if __name__ == "__main__":
    main()
