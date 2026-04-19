"use client";

import { useState, useMemo, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Activity,
  Zap,
} from "lucide-react";
import {
  useOtelSessions,
  useSessionSubscription,
  useSessionsSummary,
} from "@/hooks/use-api";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { PageHeader } from "@/components/layouts/page-header";
import { TableSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import type { OtelSession } from "@/lib/types";

/* ── Helpers ──────────────────────────────────────────────────────── */

function fmtTokens(n: number | string | undefined): string {
  if (n == null) return "0";
  const v = typeof n === "string" ? parseInt(n, 10) : n;
  if (isNaN(v) || v === 0) return "0";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
  return `${v}`;
}

function relTime(dateStr: string | undefined): string {
  if (!dateStr) return "\u2014";
  const d = new Date(dateStr.includes("T") || dateStr.includes("Z") ? dateStr : dateStr.replace(" ", "T") + "Z");
  const ms = Date.now() - d.getTime();
  const m = Math.floor(ms / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(ms / 3_600_000);
  if (h < 24) return `${h}h ago`;
  const y = new Date();
  y.setDate(y.getDate() - 1);
  const t = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === y.toDateString()) return `Yesterday ${t}`;
  return d.toLocaleDateString([], { month: "short", day: "numeric" }) + ` ${t}`;
}

function absTime(dateStr: string | undefined): string {
  if (!dateStr) return "";
  const d = new Date(dateStr.includes("T") || dateStr.includes("Z") ? dateStr : dateStr.replace(" ", "T") + "Z");
  return d.toLocaleString([], { weekday: "short", year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit" });
}

function fmtDuration(s?: string, e?: string): string {
  if (!s || !e) return "\u2014";
  const p = (v: string) => new Date(v.includes("T") || v.includes("Z") ? v : v.replace(" ", "T") + "Z");
  const ms = p(e).getTime() - p(s).getTime();
  if (ms < 0) return "\u2014";
  const totalMin = Math.floor(ms / 60_000);
  if (totalMin < 1) return "< 1m";
  const hr = Math.floor(totalMin / 60), mn = totalMin % 60;
  if (hr >= 24) { const d = Math.floor(hr / 24), r = hr % 24; return r > 0 ? `${d}d ${r}h` : `${d}d`; }
  if (hr > 0) return `${hr}h ${mn}m`;
  return `${mn}m`;
}

function fmtCredits(c: string | undefined): string {
  if (!c) return "\u2014";
  const v = parseFloat(c);
  if (isNaN(v)) return "\u2014";
  return v < 0.01 ? v.toFixed(4) : v.toFixed(2);
}

function shortModel(raw: string | undefined): string {
  if (!raw) return "";
  return raw
    .replace(/^us\.anthropic\./, "")
    .replace(/^eu\.anthropic\./, "")
    .replace(/^claude-/, "")
    .replace(/-\d{8}$/, "")
    .replace(/-v\d+:\d+$/, "");
}

function sessionLabel(row: OtelSession): { title: string; sub: string } {
  const parts: string[] = [];
  const m = shortModel(row.model);
  if (m) parts.push(m);
  const pc = Number(row.prompt_count || 0);
  if (pc > 0) parts.push(`${pc} prompt${pc !== 1 ? "s" : ""}`);

  return { title: parts.join(" \u00b7 "), sub: "" };
}

function userName(row: OtelSession): string {
  return row.user_display || (row.user_id ? row.user_id.slice(0, 8) + "\u2026" : "\u2014");
}

function SortIcon({ s }: { s: false | "asc" | "desc" }) {
  if (s === "asc") return <ArrowUp className="h-3 w-3" />;
  if (s === "desc") return <ArrowDown className="h-3 w-3" />;
  return <ArrowUpDown className="h-3 w-3 opacity-20" />;
}

/* ── Page ─────────────────────────────────────────────────────────── */

export default function TracesPage() {
  const [tab, setTab] = useState<"all" | "active">("all");
  const [platformFilter, setPlatformFilter] = useState("all");
  const [daysFilter, setDaysFilter] = useState("all");

  const filters = useMemo(() => {
    const f: { platform?: string; days?: number } = {};
    if (platformFilter !== "all") f.platform = platformFilter;
    if (daysFilter !== "all") f.days = parseInt(daysFilter, 10);
    return Object.keys(f).length > 0 ? f : undefined;
  }, [platformFilter, daysFilter]);

  const { data: sessions, isLoading, isError, error, refetch } =
    useOtelSessions({ refetchInterval: 30_000, filters });
  const { data: summary } = useSessionsSummary();
  useSessionSubscription();
  const router = useRouter();

  const [sorting, setSorting] = useState<SortingState>([{ id: "first_event_time", desc: true }]);
  const [globalFilter, setGlobalFilter] = useState("");

  const all = useMemo(() => (sessions ?? []) as OtelSession[], [sessions]);
  const activeCount = useMemo(() => all.filter((s) => s.is_active).length, [all]);
  const data = useMemo(() => (tab === "active" ? all.filter((s) => s.is_active) : all), [all, tab]);

  /* ── Columns ────────────────────────────────────────── */

  const columns = useMemo<ColumnDef<OtelSession>[]>(() => [
    {
      id: "session",
      header: "Session",
      size: 400,
      cell: ({ row }) => {
        const { title, sub } = sessionLabel(row.original);
        const display = title || sub || "Session";
        return (
          <div className="flex items-center gap-3 min-w-0">
            <div className="shrink-0 w-2.5 flex justify-center">
              {row.original.is_active ? (
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/20" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <Link
                href={`/traces/${row.original.session_id}`}
                className={`text-[13px] leading-snug block truncate transition-colors ${
                  title ? "font-medium text-foreground hover:text-primary" : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={(e) => e.stopPropagation()}
              >
                {display}
              </Link>
              {title && sub && (
                <p className="text-[11px] text-muted-foreground/40 truncate mt-0.5">{sub}</p>
              )}
            </div>
          </div>
        );
      },
      sortingFn: (a, b) => {
        const at = a.original.first_event_time ?? "";
        const bt = b.original.first_event_time ?? "";
        return at < bt ? -1 : at > bt ? 1 : 0;
      },
    },
    {
      accessorKey: "user_id",
      header: "User",
      size: 160,
      cell: ({ row }) => {
        const name = userName(row.original);
        const hasName = !!row.original.user_display;
        return (
          <span className={`text-[13px] truncate block max-w-[150px] ${hasName ? "text-foreground" : "text-muted-foreground font-mono text-xs"}`}>
            {name}
          </span>
        );
      },
    },
    {
      accessorKey: "platform",
      header: "Platform",
      size: 120,
      cell: ({ row }) => {
        const platform = row.original.platform || "Unknown";
        const ide = row.original.ide;
        return (
          <span className="text-[13px] text-muted-foreground">
            {platform}{ide ? ` \u00b7 ${ide}` : ""}
          </span>
        );
      },
    },
    {
      accessorKey: "total_input_tokens",
      header: "Tokens",
      size: 120,
      meta: { align: "center" },
      cell: ({ row }) => {
        const r = row.original;
        if (r.service_name === "kiro-cli" || r.session_id.startsWith("kiro-")) {
          return <span className="text-[13px] font-mono tabular-nums text-orange-500">{fmtCredits(r.credits)} cr</span>;
        }
        const inp = Number(r.total_input_tokens || 0) + Number(r.total_cache_read_tokens || 0);
        const out = Number(r.total_output_tokens || 0);
        return (
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="text-[13px] font-mono tabular-nums cursor-default">
                  <span className="text-emerald-600 dark:text-emerald-400">{fmtTokens(inp)}</span>
                  <span className="text-muted-foreground/20 mx-px">/</span>
                  <span className="text-blue-600 dark:text-blue-400">{fmtTokens(out)}</span>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                <div className="text-xs space-y-1 py-0.5">
                  <div className="flex justify-between gap-6"><span className="text-muted-foreground">Input</span><span className="font-mono">{Number(r.total_input_tokens || 0).toLocaleString()}</span></div>
                  {Number(r.total_cache_read_tokens || 0) > 0 && (
                    <div className="flex justify-between gap-6"><span className="text-muted-foreground">Cache</span><span className="font-mono">{Number(r.total_cache_read_tokens || 0).toLocaleString()}</span></div>
                  )}
                  <div className="flex justify-between gap-6"><span className="text-muted-foreground">Output</span><span className="font-mono">{Number(r.total_output_tokens || 0).toLocaleString()}</span></div>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        );
      },
    },
    {
      accessorKey: "tool_result_count",
      header: "Tools",
      size: 64,
      meta: { align: "center" },
      cell: ({ row }) => {
        const c = Number(row.original.tool_result_count || 0);
        return <span className="text-[13px] font-mono tabular-nums text-muted-foreground">{c || "\u2013"}</span>;
      },
    },
    {
      id: "duration",
      header: "Duration",
      size: 90,
      meta: { align: "center" },
      accessorFn: (row) => {
        if (!row.first_event_time || !row.last_event_time) return 0;
        const p = (v: string) => new Date(v.includes("T") || v.includes("Z") ? v : v.replace(" ", "T") + "Z");
        return p(row.last_event_time).getTime() - p(row.first_event_time).getTime();
      },
      cell: ({ row }) => (
        <span className="text-[13px] font-mono tabular-nums text-muted-foreground">
          {fmtDuration(row.original.first_event_time, row.original.last_event_time)}
        </span>
      ),
    },
    {
      accessorKey: "first_event_time",
      header: "Started",
      size: 110,
      meta: { align: "center" },
      cell: ({ row }) => (
        <TooltipProvider delayDuration={300}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-[13px] text-muted-foreground tabular-nums cursor-default">{relTime(row.original.first_event_time)}</span>
            </TooltipTrigger>
            <TooltipContent side="left"><span className="text-xs">{absTime(row.original.first_event_time)}</span></TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ),
    },
    {
      id: "score",
      header: "Score",
      size: 56,
      meta: { align: "center" },
      cell: () => <span className="text-[13px] text-muted-foreground/20">{"\u2014"}</span>,
      enableSorting: false,
    },
  ], []);

  const table = useReactTable({
    data, columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const [searchVal, setSearchVal] = useState("");
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);
  const onSearch = useCallback((v: string) => {
    setSearchVal(v);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => setGlobalFilter(v), 200);
  }, [setGlobalFilter]);

  return (
    <>
      <PageHeader
        title="Traces"
        breadcrumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Traces" }]}
      />

      <div className="p-6 w-full max-w-[1440px] mx-auto space-y-5">
        {isLoading ? (
          <TableSkeleton rows={8} cols={8} />
        ) : isError ? (
          <ErrorState message={error?.message} onRetry={() => refetch()} />
        ) : all.length === 0 && !filters ? (
          <EmptyState icon={Zap} title="No sessions yet" description="Sessions appear here once telemetry data is collected from your IDE." />
        ) : (
          <>
            {/* Summary */}
            <div className="flex items-center gap-6 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <Activity className="h-3.5 w-3.5" />
                <span className="font-semibold text-foreground tabular-nums">{summary?.sessions_today ?? all.length}</span>
                <span>sessions today</span>
              </span>
            </div>

            {/* Toolbar */}
            <div className="flex items-center gap-3">
              <Tabs value={tab} onValueChange={(v) => setTab(v as "all" | "active")}>
                <TabsList className="h-9 p-1">
                  <TabsTrigger value="all" className="text-xs px-3 h-7 gap-1.5 data-[state=active]:shadow-sm">
                    All
                    <span className="tabular-nums text-[10px] text-muted-foreground ml-0.5">{all.length}</span>
                  </TabsTrigger>
                  <TabsTrigger value="active" className="text-xs px-3 h-7 gap-1.5 data-[state=active]:shadow-sm">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
                    </span>
                    Active
                    {activeCount > 0 && <span className="tabular-nums text-[10px] text-emerald-600 dark:text-emerald-400 ml-0.5">{activeCount}</span>}
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              <Select value={platformFilter} onValueChange={setPlatformFilter}>
                <SelectTrigger className="w-[140px] h-9 text-xs border-dashed">
                  <SelectValue placeholder="Platform" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All platforms</SelectItem>
                  <SelectItem value="Claude Code">Claude Code</SelectItem>
                  <SelectItem value="Kiro">Kiro</SelectItem>
                </SelectContent>
              </Select>

              <Select value={daysFilter} onValueChange={setDaysFilter}>
                <SelectTrigger className="w-[120px] h-9 text-xs border-dashed">
                  <SelectValue placeholder="Time" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All time</SelectItem>
                  <SelectItem value="1">Today</SelectItem>
                  <SelectItem value="7">Last 7 days</SelectItem>
                  <SelectItem value="30">Last 30 days</SelectItem>
                </SelectContent>
              </Select>

              <div className="flex-1" />

              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/40" />
                <Input value={searchVal} onChange={(e) => onSearch(e.target.value)} placeholder="Search sessions\u2026" className="pl-9 h-9 w-64 text-xs" />
              </div>
            </div>

            {/* Table */}
            <div className="rounded-lg border border-border/60 overflow-hidden">
              <Table>
                <TableHeader>
                  {table.getHeaderGroups().map((hg) => (
                    <TableRow key={hg.id} className="hover:bg-transparent border-b border-border/60 bg-muted/30">
                      {hg.headers.map((h) => {
                        const centered = (h.column.columnDef.meta as { align?: string })?.align === "center";
                        return (
                          <TableHead
                            key={h.id}
                            className={`h-10 px-4 first:pl-5 last:pr-5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60 select-none ${
                              centered ? "text-center" : ""
                            } ${h.column.getCanSort() ? "cursor-pointer hover:text-muted-foreground transition-colors" : ""}`}
                            onClick={h.column.getToggleSortingHandler()}
                          >
                            {centered ? (
                              <span className="relative inline-flex items-center">
                                {flexRender(h.column.columnDef.header, h.getContext())}
                                {h.column.getCanSort() && (
                                  <span className="absolute -right-4 top-1/2 -translate-y-1/2">
                                    <SortIcon s={h.column.getIsSorted()} />
                                  </span>
                                )}
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1">
                                {flexRender(h.column.columnDef.header, h.getContext())}
                                {h.column.getCanSort() && <SortIcon s={h.column.getIsSorted()} />}
                              </span>
                            )}
                          </TableHead>
                        );
                      })}
                    </TableRow>
                  ))}
                </TableHeader>
                <TableBody>
                  {table.getRowModel().rows.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={columns.length} className="h-32 text-center text-sm text-muted-foreground/50">
                        No matching sessions.
                      </TableCell>
                    </TableRow>
                  ) : (
                    table.getRowModel().rows.map((row, idx) => (
                      <TableRow
                        key={row.id}
                        className={`group/row cursor-pointer transition-colors border-b border-border/30 last:border-0 hover:bg-muted/30 ${
                          idx % 2 === 1 ? "bg-muted/8" : ""
                        }`}
                        onClick={() => router.push(`/traces/${row.original.session_id}`)}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <TableCell key={cell.id} className={`py-3.5 px-4 first:pl-5 last:pr-5 ${(cell.column.columnDef.meta as { align?: string })?.align === "center" ? "text-center" : ""}`}>
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>

            {/* Footer */}
            <p className="text-[11px] text-muted-foreground/40 tabular-nums">
              Showing {table.getFilteredRowModel().rows.length} of {all.length} sessions
            </p>
          </>
        )}
      </div>
    </>
  );
}
