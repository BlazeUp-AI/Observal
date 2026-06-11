# SPDX-FileCopyrightText: 2026 Swathi Saravanan <ss4522@cornell.edu>
# SPDX-License-Identifier: AGPL-3.0-only

"""Generate synthetic MCP traces to verify Observal ingestion end-to-end.

Mimics what the Cursor MCP shim emits: one `mcp` trace per session plus a
handful of `tool_call` spans. Use this to confirm the stack ingests and
surfaces telemetry *before* wiring up a real IDE.

Usage:
    python scripts/gen_synthetic_traces.py [--sessions N] [--server URL]

Auth + server URL are read from ~/.observal/config.json (run
`observal auth login` first). Override the server with --server.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017 — runs under system python 3.9 (no datetime.UTC)

CONFIG = os.path.expanduser("~/.observal/config.json")

TOOLS = [
    ("read_file", '{"path":"src/app.py"}', '{"lines":142}', 18),
    ("list_dir", '{"path":"src/"}', '{"entries":11}', 7),
    ("grep_search", '{"query":"def handler"}', '{"matches":3}', 24),
    ("run_terminal_cmd", '{"cmd":"pytest -q"}', '{"exit_code":0,"passed":42}', 1830),
    ("edit_file", '{"path":"src/app.py"}', '{"applied":true}', 56),
]


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def build_session(ide: str = "cursor") -> dict:
    """Build one trace + several tool_call spans for a single MCP session."""
    trace_id = uuid.uuid4().hex
    session_id = f"synthetic-{ide}-{uuid.uuid4().hex[:8]}"
    start = datetime.now(UTC) - timedelta(minutes=random.randint(1, 30))
    cursor = start
    spans = []
    n = random.randint(3, len(TOOLS))
    for name, inp, out, base_latency in random.sample(TOOLS, n):
        latency = base_latency + random.randint(-5, 40)
        status = "error" if random.random() < 0.12 else "success"
        span_start = cursor
        span_end = cursor + timedelta(milliseconds=latency)
        spans.append(
            {
                "span_id": uuid.uuid4().hex,
                "trace_id": trace_id,
                "type": "tool_call",
                "name": name,
                "method": "tools/call",
                "input": inp,
                "output": out if status == "success" else None,
                "error": None if status == "success" else "tool returned non-zero",
                "status": status,
                "latency_ms": latency,
                "ide": ide,
                "tools_available": len(TOOLS),
                "tool_schema_valid": True,
                "start_time": _ts(span_start),
                "end_time": _ts(span_end),
            }
        )
        cursor = span_end + timedelta(milliseconds=random.randint(50, 400))

    trace = {
        "trace_id": trace_id,
        "trace_type": "mcp",
        "session_id": session_id,
        "ide": ide,
        "name": f"{ide} MCP session",
        "tags": ["synthetic", "sanity-check"],
        "start_time": _ts(start),
        "end_time": _ts(cursor),
    }
    return {"traces": [trace], "spans": spans}


def merge(batches: list[dict]) -> dict:
    out: dict[str, list] = {"traces": [], "spans": []}
    for b in batches:
        out["traces"].extend(b["traces"])
        out["spans"].extend(b["spans"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=3)
    ap.add_argument("--ide", default="cursor")
    ap.add_argument("--server", default=None)
    args = ap.parse_args()

    cfg = {}
    if os.path.exists(CONFIG):
        with open(CONFIG) as f:
            cfg = json.load(f)
    server = (args.server or cfg.get("server_url") or "http://localhost:8000").rstrip("/")
    token = cfg.get("access_token")
    if not token:
        raise SystemExit("No access_token in ~/.observal/config.json — run `observal auth login`.")

    batch = merge([build_session(args.ide) for _ in range(args.sessions)])
    payload = json.dumps(batch).encode()
    req = urllib.request.Request(
        f"{server}/api/v1/telemetry/ingest",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Observal-Environment": "synthetic",
        },
    )
    resp = json.load(urllib.request.urlopen(req))
    sessions = [t["session_id"] for t in batch["traces"]]
    print(
        f"POST /telemetry/ingest -> {resp}\n"
        f"  {len(batch['traces'])} traces, {len(batch['spans'])} spans across {args.sessions} {args.ide} session(s)"
    )
    for s in sessions:
        print(f"  session: {s}")


if __name__ == "__main__":
    main()
