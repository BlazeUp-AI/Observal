def generate_hook_telemetry_config(hook_listing, ide: str, server_url: str = "http://localhost:8000") -> dict:
    hook_entry = {
        "type": "http",
        "url": f"{server_url}/api/v1/telemetry/hooks",
        "headers": {"X-API-Key": "$OBSERVAL_API_KEY", "X-Observal-Hook-Id": str(hook_listing.id)},
        "timeout": 10,
    }

    if ide == "claude-code":
        hook_entry["allowedEnvVars"] = ["OBSERVAL_API_KEY"]
    elif ide not in ("kiro", "kiro-cli", "cursor"):
        return {"comment": f"IDE '{ide}' requires manual hook setup. See Observal docs for configuration."}

    event = str(hook_listing.event)
    return {"hooks": {event: [{"matcher": "*", "hooks": [hook_entry]}]}}
