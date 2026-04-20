#!/usr/bin/env bash
# observal-hook.sh — Generic Claude Code hook that forwards the JSON
# payload from stdin to the Observal hooks endpoint.
#
# If the server is unreachable, the payload is buffered locally in a
# SQLite database (~/.observal/telemetry_buffer.db) so it can be
# retried later via `observal ops sync` or on the next successful hook.
#
# Claude Code sessions are never disrupted regardless of server state.

OBSERVAL_HOOKS_URL="${OBSERVAL_HOOKS_URL:-http://localhost:8000/api/v1/otel/hooks}"
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"

# Read payload from stdin into a variable so we can reuse it
payload=$(cat)

# Try to send to server first
if echo "$payload" | curl -sf --max-time 5 -X POST "$OBSERVAL_HOOKS_URL" \
  ${OBSERVAL_USER_ID:+-H "X-Observal-User-Id: $OBSERVAL_USER_ID"} \
  ${OBSERVAL_USERNAME:+-H "X-Observal-Username: $OBSERVAL_USERNAME"} \
  -H "Content-Type: application/json" \
  -d @- >/dev/null 2>&1; then
    # Success — flush any buffered events in the background
    python3 "$HOOK_DIR/flush_buffer.py" &>/dev/null &
else
    # Server unreachable — buffer the event locally
    echo "$payload" | python3 "$HOOK_DIR/buffer_event.py" 2>/dev/null || true
fi

# Claude Code requires JSON with "continue" on stdout for the session to proceed
echo '{"continue":true}'
