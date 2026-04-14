#!/usr/bin/env python3
"""Buffer a telemetry event from stdin into the local SQLite store.

Called by the shell hook when the server is unreachable.
No dependencies beyond Python stdlib (sqlite3, json, sys, os).

When the ``cryptography`` library is installed and the server's public key
is cached locally, payloads are encrypted with ECIES before storage.
"""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".observal" / "telemetry_buffer.db"
MAX_EVENTS = 10_000


def _try_encrypt(payload: str) -> tuple[str | bytes, int]:
    """Attempt to encrypt *payload*; return (data, encrypted_flag).

    Falls back to plaintext (encrypted=0) if the crypto module or
    server public key is unavailable.
    """
    try:
        crypto_path = Path(__file__).parent / "payload_crypto.py"
        if not crypto_path.exists():
            return payload, 0
        spec = importlib.util.spec_from_file_location("payload_crypto", crypto_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if mod.can_encrypt():
            payload_bytes, was_encrypted = mod.encrypt_payload(payload)
            if was_encrypted:
                return payload_bytes, 1
    except Exception:
        pass
    return payload, 0


def main() -> None:
    payload = sys.stdin.read().strip()
    if not payload:
        return

    # Validate JSON
    try:
        json.loads(payload)
    except json.JSONDecodeError:
        return

    # Optionally encrypt before storage
    store_data, encrypted = _try_encrypt(payload)

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
                payload BLOB NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_attempt TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                encrypted INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON pending_events(status)")
        conn.execute(
            "INSERT INTO pending_events (event_type, payload, encrypted) VALUES (?, ?, ?)",
            ("hook", store_data, encrypted),
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
