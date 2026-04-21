/**
 * IDE feature capability matrix — TypeScript mirror of
 * observal-server/schemas/constants.py.
 */

export const VALID_IDES = [
  "claude-code",
  "codex",
  "copilot",
  "cursor",
  "gemini-cli",
  "kiro",
  "opencode",
  "vscode",
] as const;

export type IdeName = (typeof VALID_IDES)[number];

export const IDE_FEATURES = [
  "skills",
  "superpowers",
  "hook_bridge",
  "mcp_servers",
  "rules",
  "steering_files",
  "otlp_telemetry",
] as const;

export type IdeFeature = (typeof IDE_FEATURES)[number];

export const IDE_FEATURE_MATRIX: Record<IdeName, ReadonlySet<IdeFeature>> = {
  "claude-code": new Set(["skills", "hook_bridge", "mcp_servers", "rules", "otlp_telemetry"]),
  kiro: new Set(["superpowers", "hook_bridge", "mcp_servers", "rules", "steering_files", "otlp_telemetry"]),
  cursor: new Set(["mcp_servers", "rules"]),
  "gemini-cli": new Set(["mcp_servers", "rules"]),
  codex: new Set(["rules"]),
  copilot: new Set(["mcp_servers", "rules"]),
  opencode: new Set(["mcp_servers", "rules"]),
  vscode: new Set(["mcp_servers", "rules"]),
};

export const IDE_DISPLAY_NAMES: Record<IdeName, string> = {
  "claude-code": "Claude Code",
  kiro: "Kiro",
  cursor: "Cursor",
  "gemini-cli": "Gemini CLI",
  codex: "Codex",
  copilot: "Copilot",
  opencode: "OpenCode",
  vscode: "VS Code",
};

export const FEATURE_LABELS: Record<IdeFeature, string> = {
  skills: "Slash-command skills",
  superpowers: "Kiro superpowers",
  hook_bridge: "Hook bridge",
  mcp_servers: "MCP servers",
  rules: "Rules / system prompt",
  steering_files: "Steering files",
  otlp_telemetry: "OTLP telemetry",
};
