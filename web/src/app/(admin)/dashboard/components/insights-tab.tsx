// SPDX-License-Identifier: AGPL-3.0-only

"use client";

import { useState } from "react";
import Link from "next/link";
import { useRegistryList, useInsightReports, useGenerateInsight } from "@/hooks/use-api";
import type { RegistryItem, InsightReportListItem } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { FileText, Loader2, Sparkles } from "lucide-react";

export function InsightsTab() {
  const { data: agents, isLoading: agentsLoading } = useRegistryList("agents");
  const [selectedAgentId, setSelectedAgentId] = useState<string | undefined>(undefined);
  const { data: reports, isLoading: reportsLoading } = useInsightReports(selectedAgentId);
  const generateInsight = useGenerateInsight();

  if (agentsLoading) {
    return (
      <div className="space-y-6 pt-4">
        <div className="h-40 rounded-lg border border-border animate-pulse bg-muted/30" />
      </div>
    );
  }

  const agentList = (agents ?? []) as RegistryItem[];

  if (agentList.length === 0) {
    return (
      <div className="space-y-6 pt-4">
        <div className="rounded-md border border-border p-8 text-center text-muted-foreground">
          <FileText className="h-8 w-8 mx-auto mb-3 opacity-50" />
          <p className="text-sm font-medium mb-1">No agents available</p>
          <p className="text-xs">Deploy agents to the registry to generate insight reports.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pt-4">
      {/* Agent Picker */}
      <div className="rounded-lg border border-border p-4">
        <h3 className="text-sm font-medium mb-3">Select an Agent</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
          {agentList.slice(0, 12).map((agent) => (
            <button
              key={agent.id}
              onClick={() => setSelectedAgentId(agent.id)}
              className={`text-left p-3 rounded-md border text-sm transition-colors ${
                selectedAgentId === agent.id
                  ? "border-primary bg-primary/5 font-medium"
                  : "border-border hover:bg-muted/30"
              }`}
            >
              <span className="truncate block">{agent.name}</span>
              <span className="text-xs text-muted-foreground">{agent.version ?? ""}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Reports for Selected Agent */}
      {selectedAgentId && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium">Insight Reports</h3>
              <p className="text-xs text-muted-foreground">
                {agentList.find((a) => a.id === selectedAgentId)?.name ?? ""}
              </p>
            </div>
            <button
              onClick={() => generateInsight.mutate({ agentId: selectedAgentId })}
              disabled={generateInsight.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {generateInsight.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
              Generate Report
            </button>
          </div>

          {reportsLoading ? (
            <div className="p-6">
              <div className="h-24 animate-pulse bg-muted/30 rounded" />
            </div>
          ) : !reports || reports.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              <p className="mb-2">No insight reports for this agent yet.</p>
              <p className="text-xs">Click "Generate Report" to analyze this agent's recent sessions.</p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {(reports as InsightReportListItem[]).slice(0, 5).map((report) => (
                <Link
                  key={report.id}
                  href={`/insights/${report.id}`}
                  className="flex items-center justify-between p-4 hover:bg-muted/20 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <div className="text-sm font-medium">
                        {new Date(report.period_start).toLocaleDateString()} — {new Date(report.period_end).toLocaleDateString()}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {report.sessions_analyzed} sessions analyzed
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        (report.status === "completed" ? "default" : report.status === "failed" ? "destructive" : "secondary") as "default" | "secondary" | "destructive"
                      }
                      className="text-[10px]"
                    >
                      {report.status === "running" && <Loader2 className="h-2.5 w-2.5 animate-spin mr-1" />}
                      {report.status}
                    </Badge>
                    {report.completed_at && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(report.completed_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Enterprise notice */}
      <div className="rounded-md border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
        Agent Insights is an enterprise feature. Reports use LLM analysis to identify friction points,
        coverage gaps, and optimization opportunities per agent.
      </div>
    </div>
  );
}
