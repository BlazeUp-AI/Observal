#!/usr/bin/env python3
"""Buffer a telemetry event from stdin into the local SQLite store.

Called by the shell hook when the server is unreachable.
No dependencies beyond Python stdlib (sqlite3, json, sys, os).
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".observal" / "telemetry_buffer.db"
MAX_EVENTS = 10_000


def main() -> None:
    payload = sys.stdin.read().strip()
    if not payload:
        return

    # Validate JSON
    try:
        json.loads(payload)
    except json.JSONDecodeError:
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_attempt TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON pending_events(status)")
        conn.execute(
            "INSERT INTO pending_events (event_type, payload) VALUES (?, ?)",
            ("hook", payload),
        )
        conn.commit()

        # Enforce cap: drop oldest when over limit
        count = conn.execute("SELECT COUNT(*) FROM pending_events").fetchone()[0]
        if count > MAX_EVENTS:
            excess = count - MAX_EVENTS
            conn.execute(
                "DELETE FROM pending_events WHERE id IN (  SELECT id FROM pending_events ORDER BY id ASC LIMIT ?)",
                (excess,),
            )
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
