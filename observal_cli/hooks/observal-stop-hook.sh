#!/usr/bin/env bash
# observal-stop-hook.sh — Claude Code Stop hook that captures ALL assistant
# text responses from the current turn and sends them to Observal.
#
# The hook receives JSON on stdin with session_id, transcript_path, etc.
# It reads the transcript JSONL backwards, collecting text from every
# assistant message until it hits a user/system message (marking the
# start of the turn), then POSTs the concatenated text to the hooks endpoint.

set -eu
# NOTE: no pipefail — tac|while causes SIGPIPE when while breaks early

OBSERVAL_HOOKS_URL="${OBSERVAL_HOOKS_URL:-http://localhost:8000/api/v1/otel/hooks}"

# Read hook payload from stdin
PAYLOAD=$(cat)

SESSION_ID=$(echo "$PAYLOAD" | jq -r '.session_id // ""')
TRANSCRIPT_PATH=$(echo "$PAYLOAD" | jq -r '.transcript_path // ""')

if [ -z "$SESSION_ID" ] || [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

# Collect ALL assistant text from the current turn (bottom-up until user msg).
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

# tac reads bottom-up. We collect every assistant message's text content
# and stop when we hit a non-assistant message (user prompt = turn boundary).
(tac "$TRANSCRIPT_PATH" || true) | while IFS= read -r line; do
  # Detect message type
  case "$line" in
    *'"type":"assistant"'*)
      TEXT=$(echo "$line" | jq -r \
        '[.message.content[]? | select(.type == "text") | .text] | join("\n")' 2>/dev/null)
      if [ -n "$TEXT" ]; then
        # Prepend to tmpfile (since we're reading backwards)
        if [ -s "$TMPFILE" ]; then
          EXISTING=$(cat "$TMPFILE")
          printf '%s\n\n%s' "$TEXT" "$EXISTING" > "$TMPFILE"
        else
          printf '%s' "$TEXT" > "$TMPFILE"
        fi
      fi
      ;;
    *'"type":"user"'*|*'"type":"human"'*)
      # Hit a user message — this is the turn boundary, stop collecting
      break
      ;;
    *)
      # Skip system/tool_result/other non-assistant lines
      continue
      ;;
  esac
done

LAST_RESPONSE=$(cat "$TMPFILE" 2>/dev/null || true)

if [ -z "$LAST_RESPONSE" ]; then
  exit 0
fi

# Truncate to 64KB
LAST_RESPONSE=$(echo "$LAST_RESPONSE" | head -c 65536)

# POST to Observal
jq -n \
  --arg session_id "$SESSION_ID" \
  --arg response "$LAST_RESPONSE" \
  '{
    hook_event_name: "Stop",
    session_id: $session_id,
    tool_name: "assistant_response",
    tool_response: $response
  }' | curl -s --max-time 5 -X POST "$OBSERVAL_HOOKS_URL" \
    -H "Content-Type: application/json" \
    -d @- >/dev/null 2>&1

exit 0
