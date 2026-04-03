#!/usr/bin/env python3
"""Mock MCP server with general-purpose tools: echo, add, read_file, write_file, search."""

import json
import sys

TOOLS = [
    {
        "name": "echo",
        "description": "Echo input text back",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "add",
        "description": "Add two numbers",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file's contents",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "search",
        "description": "Search for a pattern in files",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "directory": {"type": "string"}},
            "required": ["query"],
        },
    },
]

RESOURCES = [
    {"uri": "file:///demo/config.json", "name": "Demo Config", "mimeType": "application/json"},
]

PROMPTS = [
    {"name": "summarize", "description": "Summarize text", "arguments": [{"name": "text", "required": True}]},
]


def respond(msg_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\n")
    sys.stdout.flush()


def error(msg_id, code, message):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}) + "\n")
    sys.stdout.flush()


def handle_tool_call(msg_id, name, args):
    if name == "echo":
        respond(msg_id, {"content": [{"type": "text", "text": args.get("text", "")}]})
    elif name == "add":
        respond(msg_id, {"content": [{"type": "text", "text": str(args.get("a", 0) + args.get("b", 0))}]})
    elif name == "read_file":
        path = args.get("path", "/tmp/demo.txt")
        respond(
            msg_id, {"content": [{"type": "text", "text": f"Contents of {path}:\n# Demo file\nline1\nline2\nline3"}]}
        )
    elif name == "write_file":
        respond(
            msg_id,
            {
                "content": [
                    {"type": "text", "text": f"Wrote {len(args.get('content', ''))} bytes to {args.get('path', '')}"}
                ]
            },
        )
    elif name == "search":
        q = args.get("query", "")
        respond(
            msg_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": f"Found 3 matches for '{q}':\n  src/main.py:10: {q}_handler()\n  src/utils.py:25: def {q}():\n  README.md:5: {q} documentation",
                    }
                ]
            },
        )
    else:
        error(msg_id, -32601, f"Unknown tool: {name}")


def main():
    sys.stderr.write("mock-mcp: started\n")
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
            respond(
                msg_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                    "serverInfo": {"name": "mock-mcp", "version": "1.0.0"},
                },
            )
        elif method == "tools/list":
            respond(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            handle_tool_call(msg_id, params.get("name", ""), params.get("arguments", {}))
        elif method == "resources/list":
            respond(msg_id, {"resources": RESOURCES})
        elif method == "resources/read":
            respond(
                msg_id,
                {
                    "contents": [
                        {
                            "uri": params.get("uri", ""),
                            "mimeType": "application/json",
                            "text": '{"demo": true, "version": "1.0.0"}',
                        }
                    ]
                },
            )
        elif method == "prompts/list":
            respond(msg_id, {"prompts": PROMPTS})
        elif method == "prompts/get":
            respond(
                msg_id,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": f"Please summarize: {params.get('arguments', {}).get('text', '')}",
                            },
                        }
                    ]
                },
            )
        elif method == "ping":
            respond(msg_id, {})
        else:
            respond(msg_id, {})


if __name__ == "__main__":
    main()
