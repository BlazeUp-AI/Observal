// SPDX-License-Identifier: AGPL-3.0-only

"use client";

import { useExecDepartments, useExecDeptTokens } from "@/hooks/use-api";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export function DepartmentsTab() {
  const { data: depts, isLoading: deptsLoading } = useExecDepartments();
  const { data: tokens, isLoading: tokensLoading } = useExecDeptTokens();

  if (deptsLoading) {
    return (
      <div className="space-y-6 pt-4">
        <div className="h-64 rounded-lg border border-border animate-pulse bg-muted/30" />
      </div>
    );
  }

  const departments = depts?.departments ?? [];

  if (departments.length === 0) {
    return (
      <div className="space-y-6 pt-4">
        <div className="rounded-md border border-border p-8 text-center text-muted-foreground">
          <p className="text-sm font-medium mb-2">No department data available</p>
          <p className="text-xs">
            Assign departments to users in Settings, or log in via SSO to auto-sync groups from your identity provider.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pt-4">
      {/* Department Breakdown Table */}
      <div className="rounded-lg border border-border overflow-hidden">
        <div className="p-4 border-b border-border">
          <h3 className="text-sm font-medium">Department Breakdown</h3>
          <p className="text-xs text-muted-foreground">
            {departments.length} departments · {departments.reduce((s, d) => s + d.user_count, 0)} total users
          </p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="text-left p-3 font-medium">Department</th>
              <th className="text-left p-3 font-medium">Team Size</th>
              <th className="text-left p-3 font-medium">Agents</th>
              <th className="text-left p-3 font-medium">AI Utilization</th>
              <th className="text-left p-3 font-medium">Sessions/User</th>
            </tr>
          </thead>
          <tbody>
            {departments.map((dept) => (
              <tr key={dept.department} className="border-b border-border">
                <td className="p-3 font-semibold">{dept.department}</td>
                <td className="p-3 tabular-nums">{dept.user_count}</td>
                <td className="p-3 tabular-nums font-semibold text-primary">{dept.agent_count}</td>
                <td className="p-3">
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${dept.utilization_pct}%`,
                          background: dept.utilization_pct > 80 ? "hsl(var(--success, 142 76% 36%))" : dept.utilization_pct > 50 ? "hsl(var(--primary))" : "hsl(var(--warning, 38 92% 50%))",
                        }}
                      />
                    </div>
                    <span className="tabular-nums text-xs font-semibold">{dept.utilization_pct}%</span>
                  </div>
                </td>
                <td className="p-3 tabular-nums">{dept.sessions_per_user}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Token Usage by Department */}
      <div className="rounded-lg border border-border overflow-hidden">
        <div className="p-4 border-b border-border">
          <h3 className="text-sm font-medium">Token Usage by Department</h3>
          <p className="text-xs text-muted-foreground">Cost and usage efficiency per department</p>
        </div>
        {tokensLoading ? (
          <div className="p-4">
            <div className="h-40 animate-pulse bg-muted/30 rounded" />
          </div>
        ) : !tokens || tokens.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No token usage data yet.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="text-left p-3 font-medium">Department</th>
                <th className="text-left p-3 font-medium">Tokens Used</th>
                <th className="text-left p-3 font-medium">Cost/Task</th>
                <th className="text-left p-3 font-medium">Sessions/User</th>
                <th className="text-left p-3 font-medium">Trend</th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((t) => (
                <tr key={t.department} className="border-b border-border">
                  <td className="p-3 font-semibold">{t.department}</td>
                  <td className="p-3 tabular-nums">{(t.tokens_used / 1000).toFixed(0)}K</td>
                  <td className="p-3 tabular-nums font-mono text-xs">${t.cost_per_task.toFixed(3)}</td>
                  <td className="p-3 tabular-nums">{t.sessions_per_user}</td>
                  <td className="p-3">
                    <div className="flex items-center gap-1">
                      {t.trend_pct > 0 ? (
                        <TrendingUp className="h-3 w-3 text-green-600" />
                      ) : t.trend_pct < 0 ? (
                        <TrendingDown className="h-3 w-3 text-red-600" />
                      ) : (
                        <Minus className="h-3 w-3 text-muted-foreground" />
                      )}
                      <span className={`text-xs tabular-nums ${t.trend_pct > 0 ? "text-green-600" : t.trend_pct < 0 ? "text-red-600" : "text-muted-foreground"}`}>
                        {t.trend_pct > 0 ? "+" : ""}{t.trend_pct}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
