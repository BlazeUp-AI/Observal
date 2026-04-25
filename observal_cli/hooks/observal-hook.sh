#!/usr/bin/env bash
# observal-hook.sh — Generic Claude Code hook that forwards the JSON
# payload from stdin to the Observal hooks endpoint.
#
# If the server is unreachable, the payload is buffered locally in a
# SQLite database (~/.observal/telemetry_buffer.db) so it can be
# retried later via `observal ops sync` or on the next successful hook.
#
# Claude Code sessions are never disrupted regardless of server state.

_py=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)

if [ -z "$OBSERVAL_HOOKS_URL" ]; then
  _cfg="$HOME/.observal/config.json"
  if [ -f "$_cfg" ]; then
    _srv=$($_py -c "import json,sys;print(json.load(open('$_cfg')).get('server_url',''))" 2>/dev/null || true)
    if [ -n "$_srv" ]; then
      OBSERVAL_HOOKS_URL="${_srv%/}/api/v1/telemetry/hooks"
    fi
  fi
  if [ -z "$OBSERVAL_HOOKS_URL" ]; then
    echo '{"continue":true}'
    exit 0
  fi
fi
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
    $_py "$HOOK_DIR/flush_buffer.py" &>/dev/null &
else
    # Server unreachable — buffer the event locally
    echo "$payload" | $_py "$HOOK_DIR/buffer_event.py" 2>/dev/null || true
fi

# Claude Code requires JSON with "continue" on stdout for the session to proceed
echo '{"continue":true}'
