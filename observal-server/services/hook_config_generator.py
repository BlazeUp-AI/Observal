# Shell snippet to get or create a stable session ID.
# agentSpawn creates a new UUID; all other events read the existing one.
_SESSION_FILE = "/tmp/observal-kiro-session"  # nosec B108
_SID_READ = f'$(cat {_SESSION_FILE} 2>/dev/null || echo "kiro-$PPID")'
_SID_CREATE = f'$(python3 -c "import uuid; print(uuid.uuid4())" | tee {_SESSION_FILE})'


def _unix_sed_cmd(session_expr: str, server_url: str) -> str:
    """Build the cat | sed | curl pipeline with the given session expression."""
    return (
        f'cat | sed \'s/^{{/{{"session_id":"\'"{session_expr}"\'","service_name":"kiro",'
        '"terminal_type":"\'$TERM\'","shell":"\'$SHELL\'",/\' '
        f"| curl -sf -X POST {server_url}/api/v1/otel/hooks "
        f'-H "Content-Type: application/json" '
        f"-d @-"
    )


def generate_hook_telemetry_config(
    hook_listing, ide: str, server_url: str = "http://localhost:8000", platform: str = ""
) -> dict:
    if ide in ("kiro", "kiro-cli"):
        event = str(hook_listing.event)
        # Map Claude Code PascalCase events to Kiro camelCase
        kiro_event_map = {
            "SessionStart": "agentSpawn",
            "UserPromptSubmit": "userPromptSubmit",
            "PreToolUse": "preToolUse",
            "PostToolUse": "postToolUse",
            "Stop": "stop",
        }
        kiro_event = kiro_event_map.get(event, event)

        if platform == "win32":
            # PowerShell-compatible: pipe stdin through the Python hook script.
            # No cat/sed/curl/$PPID/$TERM/$SHELL — those don't exist in PowerShell.
            if kiro_event == "stop":
                ps_stop_cmd = f"python -m observal_cli.hooks.kiro_stop_hook --url {server_url}/api/v1/otel/hooks"
                return {"hooks": {kiro_event: [{"command": ps_stop_cmd}]}}

            ps_cmd = f"python -m observal_cli.hooks.kiro_hook --url {server_url}/api/v1/otel/hooks"
            hook_entry = {"command": ps_cmd}
            if kiro_event in ("preToolUse", "postToolUse"):
                hook_entry["matcher"] = "*"
            return {"hooks": {kiro_event: [hook_entry]}}

        # Unix: use stable UUID session IDs instead of $PPID.
        # agentSpawn creates a new session; other events reuse it.
        is_session_start = kiro_event == "agentSpawn"
        sid_expr = _SID_CREATE if is_session_start else _SID_READ

        # For stop events, use the enrichment script to capture model/tokens
        if kiro_event == "stop":
            stop_cmd = (
                f'cat | sed \'s/^{{/{{"session_id":"\'"{_SID_READ}"\'","service_name":"kiro",'
                '"terminal_type":"\'$TERM\'","shell":"\'$SHELL\'",/\' '
                f"| python3 -m observal_cli.hooks.kiro_stop_hook "
                f"--url {server_url}/api/v1/otel/hooks"
            )
            return {"hooks": {kiro_event: [{"command": stop_cmd}]}}

        curl_cmd = _unix_sed_cmd(sid_expr, server_url)
        hook_entry = {"command": curl_cmd}
        if kiro_event in ("preToolUse", "postToolUse"):
            hook_entry["matcher"] = "*"
        return {"hooks": {kiro_event: [hook_entry]}}

    hook_entry = {
        "type": "http",
        "url": f"{server_url}/api/v1/otel/hooks",
        "timeout": 10,
    }

    if ide == "claude-code":
        hook_entry["allowedEnvVars"] = ["OBSERVAL_API_KEY"]
    elif ide != "cursor":
        return {"comment": f"IDE '{ide}' requires manual hook setup. See Observal docs for configuration."}

    event = str(hook_listing.event)
    return {"hooks": {event: [{"matcher": "*", "hooks": [hook_entry]}]}}
