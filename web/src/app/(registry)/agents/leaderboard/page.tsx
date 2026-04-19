"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Trophy,
  ArrowDownToLine,
  Star,
  Search,
  Blocks,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/layouts/page-header";
import { TableSkeleton } from "@/components/shared/skeleton-layouts";
import { EmptyState } from "@/components/shared/empty-state";
import { useLeaderboard, useComponentLeaderboard } from "@/hooks/use-api";
import { compactNumber } from "@/lib/utils";
import type { LeaderboardWindow } from "@/lib/types";

export default function LeaderboardPage() {
  const [activeTab, setActiveTab] = useState<"agents" | "components">("agents");
  const [window, setWindow] = useState<LeaderboardWindow>("7d");
  const [userFilterInput, setUserFilterInput] = useState("");
  const [userFilter, setUserFilter] = useState("");

  // Debounce the user filter input by 300ms
  useEffect(() => {
    const timer = setTimeout(() => setUserFilter(userFilterInput), 300);
    return () => clearTimeout(timer);
  }, [userFilterInput]);

  const { data: leaderboard, isLoading: agentsLoading } = useLeaderboard(
    window,
    50,
    userFilter || undefined,
  );
  const { data: componentLeaderboard, isLoading: componentsLoading } =
    useComponentLeaderboard();

  // Memoize sorted component leaderboard (ranked by total_downloads desc)
  const rankedComponents = useMemo(
    () =>
      componentLeaderboard
        ? [...componentLeaderboard].sort(
            (a, b) => b.total_downloads - a.total_downloads,
          )
        : [],
    [componentLeaderboard],
  );

  return (
    <>
      <PageHeader
        title="Leaderboard"
        breadcrumbs={[
          { label: "Registry", href: "/" },
          { label: "Agents", href: "/agents" },
          { label: "Leaderboard" },
        ]}
      />

      <div className="p-6 lg:p-8 w-full max-w-[1200px] mx-auto space-y-6">
        {/* Top-level Agents / Components tab switcher */}
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as "agents" | "components")}
        >
          <div className="flex items-center justify-between flex-wrap gap-4">
            <TabsList>
              <TabsTrigger value="agents">Agents</TabsTrigger>
              <TabsTrigger value="components">Components</TabsTrigger>
            </TabsList>

            {/* Time window selector -- only for Agents tab */}
            {activeTab === "agents" && (
              <Tabs
                value={window}
                onValueChange={(v) => setWindow(v as LeaderboardWindow)}
              >
                <TabsList>
                  <TabsTrigger value="24h">24h</TabsTrigger>
                  <TabsTrigger value="7d">7 days</TabsTrigger>
                  <TabsTrigger value="30d">30 days</TabsTrigger>
                  <TabsTrigger value="all">All time</TabsTrigger>
                </TabsList>
              </Tabs>
            )}
          </div>

          {/* ── Agents tab ───────────────────────────────────── */}
          <TabsContent value="agents">
            <div className="space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <p className="text-sm text-muted-foreground">
                  Agents ranked by downloads within the selected time window.
                </p>
                <div className="relative w-full sm:w-72">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Filter by email or username..."
                    value={userFilterInput}
                    onChange={(e) => setUserFilterInput(e.target.value)}
                    className="pl-9 h-9"
                  />
                </div>
              </div>

              {agentsLoading ? (
                <TableSkeleton rows={10} cols={5} />
              ) : !leaderboard || leaderboard.length === 0 ? (
                <EmptyState
                  icon={Trophy}
                  title="No rankings yet"
                  description="Install agents via the CLI or web UI to populate the leaderboard."
                />
              ) : (
                <div className="space-y-1 animate-in">
                  {/* Header */}
                  <div className="flex items-center gap-4 px-3 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    <span className="w-8 text-right">#</span>
                    <span className="flex-1">Agent</span>
                    <span className="w-24 text-right">Downloads</span>
                    <span className="w-16 text-right">Rating</span>
                    <span className="w-20 text-right">Version</span>
                  </div>

                  {leaderboard.map((item, i) => (
                    <Link
                      key={item.id}
                      href={`/agents/${item.id}`}
                      className="flex items-center gap-4 rounded-md px-3 py-3 transition-colors hover:bg-accent/40 group"
                    >
                      <span
                        className={`w-8 text-right font-mono font-semibold ${
                          i < 3 ? "text-foreground" : "text-muted-foreground"
                        }`}
                      >
                        {i + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium truncate block group-hover:underline underline-offset-4">
                          {item.name}
                        </span>
                        <span className="text-xs text-muted-foreground/70 truncate block">
                          {item.created_by_username ? `@${item.created_by_username}` : item.owner}
                          {item.description && ` — ${item.description}`}
                        </span>
                      </div>
                      <span className="w-24 text-right inline-flex items-center justify-end gap-1 text-sm text-muted-foreground font-mono">
                        <ArrowDownToLine className="h-3 w-3" />
                        {compactNumber(item.download_count)}
                      </span>
                      <span className="w-16 text-right inline-flex items-center justify-end gap-1 text-sm text-muted-foreground">
                        {item.average_rating != null ? (
                          <>
                            <Star className="h-3 w-3" />
                            {item.average_rating.toFixed(1)}
                          </>
                        ) : (
                          "-"
                        )}
                      </span>
                      <span className="w-20 text-right">
                        {item.version ? (
                          <Badge
                            variant="secondary"
                            className="text-[10px] px-1.5 py-0"
                          >
                            {item.version}
                          </Badge>
                        ) : (
                          <span className="text-sm text-muted-foreground">-</span>
                        )}
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>

          {/* ── Components tab ────────────────────────────────── */}
          <TabsContent value="components">
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                MCP components ranked by total user downloads.
              </p>

              {componentsLoading ? (
                <TableSkeleton rows={10} cols={4} />
              ) : rankedComponents.length === 0 ? (
                <EmptyState
                  icon={Blocks}
                  title="No component data yet"
                  description="Component download metrics will appear here once users install MCP components."
                />
              ) : (
                <div className="space-y-1 animate-in">
                  {/* Header */}
                  <div className="flex items-center gap-4 px-3 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    <span className="w-8 text-right">#</span>
                    <span className="flex-1">User</span>
                    <span className="w-28 text-right">MCP Count</span>
                    <span className="w-28 text-right">Downloads</span>
                  </div>

                  {rankedComponents.map((item, i) => (
                    <div
                      key={item.user}
                      className="flex items-center gap-4 rounded-md px-3 py-3 transition-colors hover:bg-accent/40"
                    >
                      <span
                        className={`w-8 text-right font-mono font-semibold ${
                          i < 3 ? "text-foreground" : "text-muted-foreground"
                        }`}
                      >
                        {i + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium truncate block">
                          {item.username ? `@${item.username}` : item.user}
                        </span>
                        {item.username && (
                          <span className="text-xs text-muted-foreground/70 truncate block">
                            {item.user}
                          </span>
                        )}
                      </div>
                      <span className="w-28 text-right inline-flex items-center justify-end gap-1 text-sm text-muted-foreground font-mono">
                        <Blocks className="h-3 w-3" />
                        {item.mcp_count}
                      </span>
                      <span className="w-28 text-right inline-flex items-center justify-end gap-1 text-sm text-muted-foreground font-mono">
                        <ArrowDownToLine className="h-3 w-3" />
                        {compactNumber(item.total_downloads)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
