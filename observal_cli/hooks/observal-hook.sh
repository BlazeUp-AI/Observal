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

# Parse --agent-name from arguments (set by per-agent frontmatter hooks)
_agent_name=""
while [ $# -gt 0 ]; do
  case "$1" in
    --agent-name) _agent_name="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Read payload from stdin into a variable so we can reuse it
payload=$(cat)

# Inject agent_name into the payload (frontmatter arg takes priority over env var)
_effective_agent="${_agent_name:-$OBSERVAL_AGENT_NAME}"
if [ -n "$_effective_agent" ]; then
  payload=$(echo "$payload" | OBSERVAL_AGENT_NAME="$_effective_agent" "$_py" -c "
import json,sys,os
d=json.load(sys.stdin)
a=os.environ.get('OBSERVAL_AGENT_NAME','')
if a and not d.get('agent_name'):
    d['agent_name']=a
print(json.dumps(d))
" 2>/dev/null || echo "$payload")
fi

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
