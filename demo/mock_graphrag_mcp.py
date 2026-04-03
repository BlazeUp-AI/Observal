#!/usr/bin/env python3
"""Mock GraphRAG MCP server: graph_query, graph_traverse, entity_lookup.

Returns fake knowledge graph data to exercise graph-specific span columns
(hop_count, entities_retrieved, relationships_used).
"""
import json
import sys

TOOLS = [
    {"name": "graph_query", "description": "Run a natural language query against the knowledge graph", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "max_hops": {"type": "integer"}}, "required": ["query"]}},
    {"name": "graph_traverse", "description": "Traverse the graph from a starting entity", "inputSchema": {"type": "object", "properties": {"entity_id": {"type": "string"}, "depth": {"type": "integer"}, "relationship_types": {"type": "array", "items": {"type": "string"}}}, "required": ["entity_id"]}},
    {"name": "entity_lookup", "description": "Look up an entity by name or ID", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
]

FAKE_ENTITIES = [
    {"id": "e-001", "name": "AuthService", "type": "service", "properties": {"language": "Python", "team": "platform"}},
    {"id": "e-002", "name": "UserDB", "type": "database", "properties": {"engine": "PostgreSQL", "tables": 12}},
    {"id": "e-003", "name": "APIGateway", "type": "service", "properties": {"language": "Go", "team": "infra"}},
    {"id": "e-004", "name": "CacheLayer", "type": "service", "properties": {"engine": "Redis", "team": "platform"}},
    {"id": "e-005", "name": "EventBus", "type": "service", "properties": {"engine": "Kafka", "team": "data"}},
]

FAKE_RELATIONSHIPS = [
    {"source": "e-001", "target": "e-002", "type": "reads_from"},
    {"source": "e-003", "target": "e-001", "type": "routes_to"},
    {"source": "e-001", "target": "e-004", "type": "caches_in"},
    {"source": "e-003", "target": "e-005", "type": "publishes_to"},
    {"source": "e-005", "target": "e-002", "type": "writes_to"},
]


def respond(msg_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\n")
    sys.stdout.flush()


def handle_tool_call(msg_id, name, args):
    if name == "graph_query":
        hops = min(args.get("max_hops", 2), 4)
        entities = FAKE_ENTITIES[:hops + 1]
        rels = FAKE_RELATIONSHIPS[:hops]
        respond(msg_id, {"content": [{"type": "text", "text": json.dumps({
            "query": args.get("query", ""),
            "hop_count": hops,
            "entities_retrieved": len(entities),
            "relationships_used": len(rels),
            "entities": entities,
            "relationships": rels,
        })}]})
    elif name == "graph_traverse":
        depth = min(args.get("depth", 2), 4)
        respond(msg_id, {"content": [{"type": "text", "text": json.dumps({
            "start_entity": args.get("entity_id", "e-001"),
            "depth": depth,
            "hop_count": depth,
            "entities_retrieved": depth + 1,
            "relationships_used": depth,
            "path": [{"entity": FAKE_ENTITIES[i % len(FAKE_ENTITIES)], "relationship": FAKE_RELATIONSHIPS[i % len(FAKE_RELATIONSHIPS)]} for i in range(depth)],
        })}]})
    elif name == "entity_lookup":
        name_q = args.get("name", "").lower()
        matches = [e for e in FAKE_ENTITIES if name_q in e["name"].lower()]
        respond(msg_id, {"content": [{"type": "text", "text": json.dumps({
            "entities_retrieved": len(matches),
            "entities": matches or [FAKE_ENTITIES[0]],
        })}]})
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Unknown tool: {name}"}}) + "\n")
        sys.stdout.flush()


def main():
    sys.stderr.write("mock-graphrag-mcp: started\n")
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
            respond(msg_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "mock-graphrag-mcp", "version": "1.0.0"}})
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
