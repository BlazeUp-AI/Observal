"use client";

import { use, useState, useCallback, useMemo } from "react";
import { useOtelSession } from "@/hooks/use-api";
import type { OtelSessionData, RawOtelEvent } from "@/lib/types";
import {
  FileText,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  Cpu,
  Wrench,
  ShieldCheck,
  MessageSquare,
  Clock,
  Zap,
  Play,
  Square,
  Globe,
  Bot,
  Search,
  Filter,
  X,
  AlertTriangle,
  Bell,
  ListChecks,
  Minimize2,
  GitBranch,
  LogIn,
} from "lucide-react";
import { PageHeader } from "@/components/layouts/page-header";
import { DetailSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/* ── Helpers ─────────────────────────────────────────────── */

function Badge({ children, variant = "default" }: { children: React.ReactNode; variant?: "default" | "success" | "warning" | "muted" }) {
  const cls = {
    default: "bg-primary/10 text-primary",
    success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    warning: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    muted: "bg-muted text-muted-foreground",
  }[variant];
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium ${cls}`}>
      {children}
    </span>
  );
}

function Stat({ label, value, icon: Icon }: { label: string; value: string | number; icon?: React.ElementType }) {
  return (
    <div className="flex items-center gap-1.5 text-xs">
      {Icon && <Icon className="h-3 w-3 text-muted-foreground shrink-0" />}
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium font-[family-name:var(--font-mono)] tabular-nums">{value}</span>
    </div>
  );
}

function formatDuration(ms: string | number): string {
  const n = typeof ms === "string" ? parseFloat(ms) : ms;
  if (n < 1000) return `${Math.round(n)}ms`;
  return `${(n / 1000).toFixed(1)}s`;
}

function formatTokens(n: string | number): string {
  const num = typeof n === "string" ? parseInt(n, 10) : n;
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}k`;
  return `${num}`;
}

function isHookEvent(eventName: string): boolean {
  return eventName.startsWith("hook_");
}

function eventIcon(eventName: string) {
  if (eventName === "api_request") return Cpu;
  if (eventName === "tool_result") return Wrench;
  if (eventName === "tool_decision") return ShieldCheck;
  if (eventName === "user_prompt" || eventName === "hook_userpromptsubmit") return MessageSquare;
  if (eventName === "hook_posttoolusetools" || eventName === "hook_posttooluse") return Wrench;
  if (eventName === "hook_pretoolusetools" || eventName === "hook_pretooluse") return ShieldCheck;
  if (eventName === "hook_posttoolusefailure") return AlertTriangle;
  if (eventName === "hook_subagentstart") return Play;
  if (eventName === "hook_subagentstop") return Square;
  if (eventName === "hook_assistant_response") return Bot;
  if (eventName === "hook_stop") return Square;
  if (eventName === "hook_stopfailure") return AlertTriangle;
  if (eventName === "hook_sessionstart") return LogIn;
  if (eventName === "hook_notification") return Bell;
  if (eventName === "hook_taskcreated" || eventName === "hook_taskcompleted") return ListChecks;
  if (eventName === "hook_precompact" || eventName === "hook_postcompact") return Minimize2;
  if (eventName === "hook_worktreecreate" || eventName === "hook_worktreeremove") return GitBranch;
  if (eventName === "hook_elicitation" || eventName === "hook_elicitationresult") return Globe;
  if (isHookEvent(eventName)) return Zap;
  return FileText;
}

function eventColor(eventName: string): string {
  if (eventName === "api_request") return "text-blue-500";
  if (eventName === "tool_result") return "text-emerald-500";
  if (eventName === "tool_decision") return "text-amber-500";
  if (eventName === "user_prompt" || eventName === "hook_userpromptsubmit") return "text-purple-500";
  if (eventName === "hook_posttooluse") return "text-cyan-500";
  if (eventName === "hook_pretooluse") return "text-sky-400";
  if (eventName === "hook_posttoolusefailure" || eventName === "hook_stopfailure") return "text-red-500";
  if (eventName === "hook_subagentstart" || eventName === "hook_subagentstop") return "text-indigo-500";
  if (eventName === "hook_assistant_response") return "text-violet-500";
  if (eventName === "hook_stop") return "text-rose-500";
  if (eventName === "hook_sessionstart") return "text-green-500";
  if (eventName === "hook_notification") return "text-yellow-500";
  if (eventName === "hook_taskcreated" || eventName === "hook_taskcompleted") return "text-lime-500";
  if (eventName === "hook_precompact" || eventName === "hook_postcompact") return "text-slate-400";
  if (eventName === "hook_worktreecreate" || eventName === "hook_worktreeremove") return "text-amber-400";
  if (eventName === "hook_elicitation" || eventName === "hook_elicitationresult") return "text-teal-500";
  if (isHookEvent(eventName)) return "text-orange-500";
  return "text-muted-foreground";
}

/* ── Filter categories ───────────────────────────────────── */

type FilterCategory = {
  key: string;
  label: string;
  match: (eventName: string) => boolean;
  color: string;
};

const FILTER_CATEGORIES: FilterCategory[] = [
  { key: "prompts", label: "Prompts", match: (e) => e === "user_prompt" || e === "hook_userpromptsubmit", color: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20" },
  { key: "responses", label: "Responses", match: (e) => e === "hook_assistant_response", color: "bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20" },
  { key: "tools", label: "Tools", match: (e) => ["tool_result", "tool_decision", "hook_posttooluse", "hook_pretooluse", "hook_posttoolusefailure"].includes(e), color: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20" },
  { key: "api", label: "API", match: (e) => e === "api_request", color: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20" },
  { key: "agents", label: "Agents", match: (e) => e === "hook_subagentstart" || e === "hook_subagentstop", color: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20" },
  { key: "lifecycle", label: "Lifecycle", match: (e) => ["hook_sessionstart", "hook_stop", "hook_stopfailure", "hook_precompact", "hook_postcompact"].includes(e), color: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20" },
  { key: "tasks", label: "Tasks", match: (e) => e === "hook_taskcreated" || e === "hook_taskcompleted", color: "bg-lime-500/10 text-lime-600 dark:text-lime-400 border-lime-500/20" },
  { key: "mcp", label: "MCP", match: (e) => e === "hook_elicitation" || e === "hook_elicitationresult", color: "bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/20" },
  { key: "errors", label: "Errors", match: (e) => e === "hook_posttoolusefailure" || e === "hook_stopfailure", color: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20" },
];

/* ── Event inline summary (shown without expanding) ────── */

function EventSummary({ event }: { event: RawOtelEvent }) {
  const attrs = event.attributes ?? {};
  const eName = attrs["event.name"] || event.event_name;

  if (eName === "api_request") {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge>{attrs.model || "?"}</Badge>
        {attrs.duration_ms && <Stat label="" value={formatDuration(attrs.duration_ms)} icon={Clock} />}
        {attrs.input_tokens && parseInt(attrs.input_tokens) > 1 && <Stat label="in" value={formatTokens(attrs.input_tokens)} />}
        {attrs.output_tokens && <Stat label="out" value={formatTokens(attrs.output_tokens)} />}
        {attrs.cache_read_tokens && parseInt(attrs.cache_read_tokens) > 0 && (
          <Stat label="cache" value={formatTokens(attrs.cache_read_tokens)} />
        )}
      </div>
    );
  }

  if (eName === "tool_result") {
    const success = attrs.success === "true";
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant={success ? "success" : "warning"}>{attrs.tool_name || "?"}</Badge>
        {attrs.duration_ms && <Stat label="" value={formatDuration(attrs.duration_ms)} icon={Clock} />}
        {attrs.tool_result_size_bytes && (
          <Stat label="size" value={`${formatTokens(attrs.tool_result_size_bytes)}B`} />
        )}
        {!success && <Badge variant="warning">failed</Badge>}
      </div>
    );
  }

  if (eName === "tool_decision") {
    const accepted = attrs.decision === "accept";
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant={accepted ? "muted" : "warning"}>{attrs.tool_name || "?"}</Badge>
        <span className="text-xs text-muted-foreground">
          {accepted ? "accepted" : "rejected"} via {attrs.source || "?"}
        </span>
      </div>
    );
  }

  if (eName === "user_prompt") {
    return (
      <div className="flex items-center gap-3">
        {attrs.prompt_length && <Stat label="length" value={`${attrs.prompt_length} chars`} />}
      </div>
    );
  }

  // Hook: user prompt
  if (eName === "hook_userpromptsubmit") {
    const preview = (attrs.tool_input || "").slice(0, 120);
    return (
      <div className="flex items-center gap-3 flex-wrap min-w-0">
        <Badge variant="default">prompt</Badge>
        {preview && <span className="text-xs text-muted-foreground truncate max-w-md">{preview}{(attrs.tool_input?.length ?? 0) > 120 ? "..." : ""}</span>}
        {attrs.prompt_length && <Stat label="" value={`${attrs.prompt_length} chars`} />}
      </div>
    );
  }

  // Hook: tool use (PostToolUse / PreToolUse)
  if (eName === "hook_posttooluse" || eName === "hook_pretooluse") {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant={eName === "hook_posttooluse" ? "success" : "muted"}>{attrs.tool_name || "?"}</Badge>
        <span className="text-[11px] text-muted-foreground">{attrs.hook_event}</span>
      </div>
    );
  }

  // Hook: subagent events
  if (eName === "hook_subagentstart" || eName === "hook_subagentstop") {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant="default">{attrs.agent_type || "agent"}</Badge>
        <span className="text-xs text-muted-foreground">{eName === "hook_subagentstart" ? "spawned" : "finished"}</span>
      </div>
    );
  }

  // Hook: MCP elicitation
  if (eName === "hook_elicitation" || eName === "hook_elicitationresult") {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant="default">{attrs.mcp_server_name || "MCP"}</Badge>
        <span className="text-xs text-muted-foreground">{eName === "hook_elicitation" ? "requesting input" : "got response"}</span>
      </div>
    );
  }

  // Hook: assistant response (Claude's text output)
  if (eName === "hook_assistant_response") {
    const preview = (attrs.tool_response || "").slice(0, 140);
    return (
      <div className="flex items-center gap-3 flex-wrap min-w-0">
        <Badge variant="default">response</Badge>
        {preview && <span className="text-xs text-muted-foreground truncate max-w-lg">{preview}{(attrs.tool_response?.length ?? 0) > 140 ? "..." : ""}</span>}
      </div>
    );
  }

  // Hook: stop
  if (eName === "hook_stop") {
    return (
      <div className="flex items-center gap-3">
        <Badge variant="muted">{attrs.stop_reason || "end_turn"}</Badge>
      </div>
    );
  }

  // Hook: tool failure
  if (eName === "hook_posttoolusefailure") {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant="warning">{attrs.tool_name || "?"}</Badge>
        <span className="text-xs text-red-500">failed</span>
        {attrs.error && <span className="text-xs text-muted-foreground truncate max-w-md">{attrs.error.slice(0, 100)}</span>}
      </div>
    );
  }

  // Hook: stop failure (API error)
  if (eName === "hook_stopfailure") {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant="warning">API error</Badge>
        {attrs.error && <span className="text-xs text-red-500 truncate max-w-md">{attrs.error.slice(0, 100)}</span>}
      </div>
    );
  }

  // Hook: session start
  if (eName === "hook_sessionstart") {
    return (
      <div className="flex items-center gap-3">
        <Badge variant="success">{attrs.session_resumed === "True" ? "resumed" : "new session"}</Badge>
      </div>
    );
  }

  // Hook: notification
  if (eName === "hook_notification") {
    const title = attrs.notification_title || "";
    const msg = (attrs.tool_response || "").slice(0, 100);
    return (
      <div className="flex items-center gap-3 flex-wrap">
        {title && <Badge variant="default">{title}</Badge>}
        {msg && <span className="text-xs text-muted-foreground truncate max-w-md">{msg}</span>}
      </div>
    );
  }

  // Hook: tasks
  if (eName === "hook_taskcreated" || eName === "hook_taskcompleted") {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant={eName === "hook_taskcompleted" ? "success" : "default"}>
          {attrs.task_subject || attrs.task_id || "task"}
        </Badge>
        <span className="text-xs text-muted-foreground">{eName === "hook_taskcreated" ? "created" : "completed"}</span>
      </div>
    );
  }

  // Hook: compaction
  if (eName === "hook_precompact" || eName === "hook_postcompact") {
    return (
      <div className="flex items-center gap-3">
        <Badge variant="muted">{eName === "hook_precompact" ? "compacting context" : "context compacted"}</Badge>
      </div>
    );
  }

  // Hook: worktree
  if (eName === "hook_worktreecreate" || eName === "hook_worktreeremove") {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant="default">{attrs.branch || "worktree"}</Badge>
        <span className="text-xs text-muted-foreground">{eName === "hook_worktreecreate" ? "created" : "removed"}</span>
      </div>
    );
  }

  // Generic hook events
  if (isHookEvent(eName)) {
    const hookType = attrs.hook_event || eName.replace("hook_", "");
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant="default">{attrs.tool_name || attrs.agent_type || "?"}</Badge>
        <span className="text-xs text-muted-foreground">{hookType}</span>
      </div>
    );
  }

  return null;
}

/* ── Pretty JSON / content block ──────────────────────── */

function ContentBlock({ label, content }: { label: string; content: string }) {
  // Try to parse and pretty-print JSON
  let display = content;
  let isJson = false;
  try {
    const parsed = JSON.parse(content);
    display = JSON.stringify(parsed, null, 2);
    isJson = true;
  } catch {
    // Not JSON — show as-is
  }

  const lines = display.split("\n").length;
  const isLong = lines > 20;
  const [showFull, setShowFull] = useState(false);

  const shown = isLong && !showFull ? display.split("\n").slice(0, 20).join("\n") + "\n..." : display;

  return (
    <div className="space-y-1">
      <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
      <pre className={`text-xs font-[family-name:var(--font-mono)] whitespace-pre-wrap break-all bg-background/50 border border-border rounded-md p-2.5 max-h-[400px] overflow-auto ${isJson ? "text-foreground" : "text-foreground/80"}`}>
        {shown}
      </pre>
      {isLong && (
        <button
          type="button"
          onClick={() => setShowFull(!showFull)}
          className="text-[11px] text-primary-accent hover:underline"
        >
          {showFull ? "Show less" : `Show all ${lines} lines`}
        </button>
      )}
    </div>
  );
}

/* ── Event detail (shown when expanded) ────────────────── */

function EventDetail({ event }: { event: RawOtelEvent }) {
  const attrs = event.attributes ?? {};
  const eName = attrs["event.name"] || event.event_name;

  // For hook events, show tool_input and tool_response as rich content blocks
  if (isHookEvent(eName) && (attrs.tool_input || attrs.tool_response)) {
    return (
      <div className="ml-6 mr-3 mb-2 mt-1 space-y-3">
        {attrs.tool_input && (
          <ContentBlock label="Input" content={attrs.tool_input} />
        )}
        {attrs.tool_response && (
          <ContentBlock label="Response" content={attrs.tool_response} />
        )}
        {/* Show other attrs in a compact grid below */}
        <HookMetaGrid attrs={attrs} />
      </div>
    );
  }

  // Default: attribute grid for OTEL events
  const skip = new Set(["event.name", "event.sequence", "event.timestamp", "session.id", "user.id", "terminal.type", "prompt.id"]);
  const entries = Object.entries(attrs)
    .filter(([k]) => !skip.has(k))
    .sort(([a], [b]) => a.localeCompare(b));

  if (entries.length === 0) return null;

  return (
    <div className="ml-6 mr-3 mb-2 mt-1">
      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-xs font-[family-name:var(--font-mono)] bg-surface-sunken rounded-md p-3">
        {entries.map(([key, value]) => (
          <div key={key} className="contents">
            <span className="text-muted-foreground">{key}</span>
            <span className="text-foreground truncate">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HookMetaGrid({ attrs }: { attrs: Record<string, string> }) {
  const skip = new Set(["event.name", "session.id", "tool_input", "tool_response", "hook_event", "tool_name"]);
  const entries = Object.entries(attrs)
    .filter(([k]) => !skip.has(k))
    .sort(([a], [b]) => a.localeCompare(b));
  if (entries.length === 0) return null;
  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-xs font-[family-name:var(--font-mono)] bg-surface-sunken rounded-md p-2">
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <span className="text-muted-foreground">{key}</span>
          <span className="text-foreground truncate">{value}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Event row ─────────────────────────────────────────── */

function EventRow({
  event,
  isExpanded,
  onToggle,
}: {
  event: RawOtelEvent;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const attrs = event.attributes ?? {};
  const eName = attrs["event.name"] || event.event_name;
  const Icon = eventIcon(eName);
  const color = eventColor(eName);

  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center gap-2 w-full text-left py-2 px-3 rounded-md hover:bg-muted/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/20"
      >
        {isExpanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        )}
        <Icon className={`h-3.5 w-3.5 shrink-0 ${color}`} />
        <span className="text-sm font-medium w-28 shrink-0">
          {eName === "hook_assistant_response" ? "response" :
           eName === "hook_userpromptsubmit" ? "prompt" :
           eName === "hook_posttooluse" ? (attrs.tool_name || "tool") :
           eName === "hook_pretooluse" ? (attrs.tool_name || "tool") :
           eName === "hook_posttoolusefailure" ? (attrs.tool_name || "tool fail") :
           eName === "hook_subagentstart" ? "agent start" :
           eName === "hook_subagentstop" ? "agent stop" :
           eName === "hook_stop" ? "turn end" :
           eName === "hook_stopfailure" ? "API error" :
           eName === "hook_sessionstart" ? "session" :
           eName === "hook_notification" ? "notify" :
           eName === "hook_taskcreated" ? "task new" :
           eName === "hook_taskcompleted" ? "task done" :
           eName === "hook_precompact" ? "compact" :
           eName === "hook_postcompact" ? "compacted" :
           eName === "hook_worktreecreate" ? "worktree+" :
           eName === "hook_worktreeremove" ? "worktree-" :
           eName === "hook_elicitation" ? "MCP ask" :
           eName === "hook_elicitationresult" ? "MCP reply" :
           isHookEvent(eName) ? (attrs.tool_name || eName) :
           eName}
        </span>
        {attrs.agent_id && (
          <span className="text-[10px] px-1 py-0.5 rounded bg-indigo-500/10 text-indigo-500 font-medium shrink-0">
            {attrs.agent_type || "agent"}
          </span>
        )}
        <div className="flex-1 min-w-0">
          <EventSummary event={event} />
        </div>
        {event.timestamp && (
          <span className="ml-auto text-[11px] text-muted-foreground tabular-nums shrink-0 pl-2">
            {new Date(event.timestamp).toLocaleTimeString()}
          </span>
        )}
      </button>
      {isExpanded && <EventDetail event={event} />}
    </div>
  );
}

/* ── Session summary stats ─────────────────────────────── */

function SessionStats({ events }: { events: RawOtelEvent[] }) {
  const stats = useMemo(() => {
    let totalInputTokens = 0;
    let totalOutputTokens = 0;
    let totalCacheRead = 0;
    let apiCalls = 0;
    let toolCalls = 0;
    let hookEvents = 0;
    const models = new Set<string>();
    const tools: Record<string, number> = {};

    for (const evt of events) {
      const attrs = evt.attributes ?? {};
      const eName = attrs["event.name"] || evt.event_name;

      if (eName === "api_request") {
        apiCalls++;
        if (attrs.input_tokens) totalInputTokens += parseInt(attrs.input_tokens, 10);
        if (attrs.output_tokens) totalOutputTokens += parseInt(attrs.output_tokens, 10);
        if (attrs.cache_read_tokens) totalCacheRead += parseInt(attrs.cache_read_tokens, 10);
        if (attrs.model) models.add(attrs.model);
      }

      if (eName === "tool_result") {
        toolCalls++;
        const tn = attrs.tool_name || "unknown";
        tools[tn] = (tools[tn] || 0) + 1;
      }

      if (isHookEvent(eName)) {
        hookEvents++;
        if (attrs.tool_name) {
          const tn = attrs.tool_name;
          tools[tn] = (tools[tn] || 0) + 1;
        }
      }
    }

    return { totalInputTokens, totalOutputTokens, totalCacheRead, apiCalls, toolCalls, hookEvents, models, tools };
  }, [events]);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
      <div className="space-y-1">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Input Tokens</p>
        <p className="text-lg font-semibold tabular-nums">{formatTokens(stats.totalInputTokens)}</p>
      </div>
      <div className="space-y-1">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Output Tokens</p>
        <p className="text-lg font-semibold tabular-nums">{formatTokens(stats.totalOutputTokens)}</p>
      </div>
      <div className="space-y-1">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Cache Read</p>
        <p className="text-lg font-semibold tabular-nums">{formatTokens(stats.totalCacheRead)}</p>
      </div>
      <div className="space-y-1">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wide">API Calls</p>
        <p className="text-lg font-semibold tabular-nums">{stats.apiCalls}</p>
      </div>
      <div className="space-y-1">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Tool Calls</p>
        <p className="text-lg font-semibold tabular-nums">{stats.toolCalls}</p>
      </div>
      {stats.hookEvents > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Hook Captures</p>
          <p className="text-lg font-semibold tabular-nums text-orange-500">{stats.hookEvents}</p>
        </div>
      )}
      <div className="space-y-1">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Models</p>
        <div className="flex flex-wrap gap-1">
          {[...stats.models].map((m) => (
            <Badge key={m}>{m.replace("claude-", "")}</Badge>
          ))}
        </div>
      </div>
      {Object.keys(stats.tools).length > 0 && (
        <div className="col-span-full space-y-1">
          <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Tools Used</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(stats.tools)
              .sort(([, a], [, b]) => b - a)
              .map(([tool, count]) => (
                <Badge key={tool} variant="muted">
                  {tool} ({count})
                </Badge>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Page ───────────────────────────────────────────────── */

export default function TraceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading, isError, error, refetch } = useOtelSession(id);

  const session = data as OtelSessionData;
  const events: RawOtelEvent[] = useMemo(() => session?.events ?? [], [session]);

  const [expandedSet, setExpandedSet] = useState<Set<number>>(new Set());
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");

  const toggleFilter = useCallback((key: string) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setActiveFilters(new Set());
    setSearchQuery("");
  }, []);

  // Filter + search events
  const filteredEvents = useMemo(() => {
    let result = events;
    // Apply category filters (OR within active filters)
    if (activeFilters.size > 0) {
      const activeCategories = FILTER_CATEGORIES.filter((c) => activeFilters.has(c.key));
      result = result.filter((evt) => {
        const eName = evt.attributes?.["event.name"] || evt.event_name;
        return activeCategories.some((cat) => cat.match(eName));
      });
    }
    // Apply search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((evt) => {
        const attrs = evt.attributes ?? {};
        const eName = attrs["event.name"] || evt.event_name;
        // Search across: event name, tool name, body, tool_input, tool_response, agent_type
        return (
          eName.toLowerCase().includes(q) ||
          (evt.body || "").toLowerCase().includes(q) ||
          (attrs.tool_name || "").toLowerCase().includes(q) ||
          (attrs.tool_input || "").toLowerCase().includes(q) ||
          (attrs.tool_response || "").toLowerCase().includes(q) ||
          (attrs.agent_type || "").toLowerCase().includes(q) ||
          (attrs.agent_id || "").toLowerCase().includes(q) ||
          (attrs.error || "").toLowerCase().includes(q) ||
          (attrs.task_subject || "").toLowerCase().includes(q)
        );
      });
    }
    return result;
  }, [events, activeFilters, searchQuery]);

  // Count events per filter category (on full event set, not filtered)
  const filterCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const cat of FILTER_CATEGORIES) {
      counts[cat.key] = events.filter((evt) => {
        const eName = evt.attributes?.["event.name"] || evt.event_name;
        return cat.match(eName);
      }).length;
    }
    return counts;
  }, [events]);

  const toggleEvent = useCallback((index: number) => {
    setExpandedSet((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    setExpandedSet((prev) => {
      if (prev.size === filteredEvents.length) {
        return new Set();
      }
      return new Set(filteredEvents.map((_, i) => i));
    });
  }, [filteredEvents]);

  const allExpanded = expandedSet.size === filteredEvents.length && filteredEvents.length > 0;

  return (
    <>
      <PageHeader
        title={isLoading ? "Session" : id.slice(0, 16) + "..."}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Traces", href: "/traces" },
          { label: id.slice(0, 12) + "..." },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {isLoading ? (
          <DetailSkeleton />
        ) : isError ? (
          <ErrorState message={error?.message} onRetry={() => refetch()} />
        ) : !data ? (
          <ErrorState message="Session not found" />
        ) : (
          <>
            {/* Header info */}
            <div className="animate-in flex flex-wrap items-center gap-x-6 gap-y-2">
              <div>
                <span className="text-xs text-muted-foreground block mb-0.5">Session ID</span>
                <span className="text-sm font-[family-name:var(--font-mono)]">{id}</span>
              </div>
              {session.service_name && (
                <div>
                  <span className="text-xs text-muted-foreground block mb-0.5">Service</span>
                  <span className="text-sm">{session.service_name}</span>
                </div>
              )}
              {events.length > 0 && events[0]?.timestamp && (
                <div>
                  <span className="text-xs text-muted-foreground block mb-0.5">First Event</span>
                  <span className="text-sm tabular-nums">{new Date(events[0].timestamp).toLocaleString()}</span>
                </div>
              )}
              {events.length > 0 && (
                <div>
                  <span className="text-xs text-muted-foreground block mb-0.5">Duration</span>
                  <span className="text-sm tabular-nums">
                    {events.length > 1 && events[events.length - 1]?.timestamp && events[0]?.timestamp
                      ? formatDuration(
                          new Date(events[events.length - 1].timestamp).getTime() -
                            new Date(events[0].timestamp).getTime()
                        )
                      : "-"}
                  </span>
                </div>
              )}
            </div>

            <Separator />

            {/* Session summary */}
            <SessionStats events={events} />

            <Separator />

            {/* Events */}
            {events.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="No events in this session"
                description="Events will appear here once telemetry data is recorded."
              />
            ) : (
              <div className="animate-in stagger-1 space-y-0.5">
                {/* Search + Filter bar */}
                <div className="space-y-2 mb-3">
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1 max-w-sm">
                      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                      <Input
                        placeholder="Search events, tools, content..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-8 h-8 text-sm"
                      />
                      {searchQuery && (
                        <button
                          type="button"
                          onClick={() => setSearchQuery("")}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={toggleAll}
                      className="h-8 text-xs gap-1"
                    >
                      <ChevronsUpDown className="h-3 w-3" />
                      {allExpanded ? "Collapse" : "Expand"}
                    </Button>
                  </div>
                  {/* Filter chips */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <Filter className="h-3 w-3 text-muted-foreground shrink-0" />
                    {FILTER_CATEGORIES.filter((cat) => filterCounts[cat.key] > 0).map((cat) => (
                      <button
                        type="button"
                        key={cat.key}
                        onClick={() => toggleFilter(cat.key)}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border transition-all ${
                          activeFilters.has(cat.key)
                            ? cat.color + " border-current"
                            : "bg-muted/50 text-muted-foreground border-transparent hover:bg-muted"
                        }`}
                      >
                        {cat.label}
                        <span className="opacity-60">{filterCounts[cat.key]}</span>
                      </button>
                    ))}
                    {(activeFilters.size > 0 || searchQuery) && (
                      <button
                        type="button"
                        onClick={clearFilters}
                        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-3 w-3" /> Clear
                      </button>
                    )}
                  </div>
                </div>

                {/* Event count */}
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">
                    {filteredEvents.length === events.length
                      ? `${events.length} event${events.length !== 1 ? "s" : ""}`
                      : `${filteredEvents.length} of ${events.length} events`}
                  </span>
                </div>

                {/* Event list */}
                {filteredEvents.length === 0 ? (
                  <div className="text-center py-8 text-sm text-muted-foreground">
                    No events match your filters.
                  </div>
                ) : (
                  filteredEvents.map((evt: RawOtelEvent, i: number) => (
                    <div key={i}>
                      <EventRow
                        event={evt}
                        isExpanded={expandedSet.has(i)}
                        onToggle={() => toggleEvent(i)}
                      />
                      {i < filteredEvents.length - 1 && <Separator className="my-0" />}
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
