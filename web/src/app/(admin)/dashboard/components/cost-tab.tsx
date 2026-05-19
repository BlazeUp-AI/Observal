// SPDX-License-Identifier: AGPL-3.0-only

"use client";

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Line } from "recharts";
import { useExecCostSummary } from "@/hooks/use-api";
import { StatCard } from "./stat-card";

export function CostTab() {
  const { data: cost, isLoading } = useExecCostSummary();

  if (isLoading) {
    return (
      <div className="space-y-6 pt-4">
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 rounded-lg border border-border animate-pulse bg-muted/30" />
          ))}
        </div>
        <div className="h-64 rounded-lg border border-border animate-pulse bg-muted/30" />
      </div>
    );
  }

  if (!cost?.configured) {
    return (
      <div className="space-y-6 pt-4">
        <div className="rounded-md border border-dashed border-border p-8 text-center">
          <p className="text-sm font-medium mb-2">Cost baselines not configured</p>
          <p className="text-xs text-muted-foreground mb-4">
            To see cost savings and ROI data, configure your pre-AI cost baselines in Settings.
            This tells the dashboard what tasks cost before AI agents were deployed.
          </p>
          <a
            href="/settings"
            className="inline-flex items-center px-4 py-2 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90"
          >
            Configure Baselines
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pt-4">
      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Monthly Savings" value={`$${(cost.monthly_savings / 1000).toFixed(1)}K`} />
        <StatCard label="Cost Reduction" value={`${cost.cost_reduction_pct}%`} />
        <StatCard label="Projected Annual" value={`$${(cost.projected_annual_savings / 1000).toFixed(0)}K`} />
        <StatCard label="Cost per Task" value={`$${cost.cost_per_task.toFixed(3)}`} />
      </div>

      {/* Savings vs Spend Chart */}
      <div className="rounded-lg border border-border p-4">
        <h3 className="text-sm font-medium mb-1">Savings vs AI Spend</h3>
        <p className="text-xs text-muted-foreground mb-4">Monthly savings generated vs platform spend</p>
        {cost.monthly_trend.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={cost.monthly_trend} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
              <defs>
                <linearGradient id="savingsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#16a34a" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
              <XAxis dataKey="month" className="text-xs" />
              <YAxis className="text-xs" tickFormatter={(v) => `$${(v / 1000).toFixed(1)}K`} />
              <Tooltip
                formatter={(value: number, name: string) => [`$${value.toFixed(2)}`, name === "savings" ? "Savings" : "AI Spend"]}
              />
              <Area type="monotone" dataKey="savings" stroke="#16a34a" strokeWidth={2.5} fill="url(#savingsGrad)" />
              <Line type="monotone" dataKey="ai_spend" stroke="#e11d48" strokeWidth={2} strokeDasharray="4 4" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">
            No cost data available yet — spans need a populated cost column.
          </div>
        )}
        <div className="flex gap-4 mt-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-3 h-0.5 bg-green-600 rounded" />
            <span>Savings</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-0.5 bg-red-600 rounded border-dashed" />
            <span>AI Spend</span>
          </div>
        </div>
      </div>

      {/* Cost per Category */}
      {cost.by_category.length > 0 && (
        <div className="rounded-lg border border-border p-4">
          <h3 className="text-sm font-medium mb-1">Cost per Task by Category</h3>
          <p className="text-xs text-muted-foreground mb-4">Pre-AI baseline vs actual AI cost</p>
          <div className="space-y-4">
            {cost.by_category.map((cat) => (
              <div key={cat.category} className="flex items-center gap-3">
                <span className="text-sm w-32 truncate font-medium">{cat.category}</span>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <div
                      className="h-1.5 bg-muted-foreground/30 rounded-full"
                      style={{ width: `${Math.min((cat.baseline_cost / (cost.by_category[0]?.baseline_cost || 1)) * 100, 100)}%` }}
                    />
                    <span className="text-xs text-muted-foreground">${cat.baseline_cost.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div
                      className="h-1.5 bg-green-600 rounded-full"
                      style={{ width: `${Math.min((cat.actual_cost / (cost.by_category[0]?.baseline_cost || 1)) * 100, 100)}%` }}
                    />
                    <span className="text-xs text-green-600 font-semibold">${cat.actual_cost.toFixed(2)}</span>
                  </div>
                </div>
                <span className="text-xs font-semibold text-green-600 bg-green-50 dark:bg-green-950 px-2 py-0.5 rounded">
                  {cat.saved_pct}%
                </span>
              </div>
            ))}
          </div>
          <div className="flex gap-4 mt-4 pt-3 border-t border-border text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="w-3 h-1.5 bg-muted-foreground/30 rounded" />
              <span>Before (manual)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-1.5 bg-green-600 rounded" />
              <span>After (AI agents)</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
