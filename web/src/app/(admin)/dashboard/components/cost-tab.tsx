// SPDX-License-Identifier: AGPL-3.0-only

"use client";

import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Line } from "recharts";
import { useExecCostSummary, useExecConfig } from "@/hooks/use-api";
import { exec } from "@/lib/api";
import { StatCard } from "./stat-card";
import { Loader2 } from "lucide-react";

const DEFAULT_CATEGORIES = [
  "Code Review",
  "Testing",
  "Documentation",
  "Incident Response",
  "Deployment",
  "Security Scanning",
];

function BaselinesConfigForm({ onSaved }: { onSaved: () => void }) {
  const [hourlyDevCost, setHourlyDevCost] = useState("75");
  const [baselines, setBaselines] = useState<Record<string, string>>(
    Object.fromEntries(DEFAULT_CATEGORIES.map((c) => [c, ""]))
  );
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const preAiBaselines: Record<string, number> = {};
      for (const [key, val] of Object.entries(baselines) as [string, string][]) {
        const num = parseFloat(val);
        if (!isNaN(num) && num > 0) preAiBaselines[key] = num;
      }
      await exec.updateConfig({
        hourly_dev_cost: parseFloat(hourlyDevCost) || 75,
        pre_ai_baselines: preAiBaselines,
      });
      onSaved();
    } catch {
      // error handled by React Query elsewhere
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 pt-4">
      <div className="rounded-lg border border-border p-6 max-w-2xl">
        <h3 className="text-sm font-semibold mb-1">Configure Cost Baselines</h3>
        <p className="text-xs text-muted-foreground mb-6">
          Enter what tasks cost before AI agents were deployed. This allows the dashboard to compute savings and ROI.
        </p>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium">Hourly Developer Cost ($)</label>
            <input
              type="number"
              value={hourlyDevCost}
              onChange={(e) => setHourlyDevCost(e.target.value)}
              className="flex h-8 w-40 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              placeholder="75"
            />
            <p className="text-[11px] text-muted-foreground">Used to compute developer hours reclaimed.</p>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium">Pre-AI Cost per Task by Category ($)</label>
            <p className="text-[11px] text-muted-foreground mb-2">
              Average cost to complete one task manually, before AI. Leave blank for categories that don't apply.
            </p>
            <div className="grid grid-cols-2 gap-3">
              {DEFAULT_CATEGORIES.map((cat) => (
                <div key={cat} className="flex items-center gap-2">
                  <span className="text-xs w-32 truncate">{cat}</span>
                  <input
                    type="number"
                    value={baselines[cat] ?? ""}
                    onChange={(e) => setBaselines({ ...baselines, [cat]: e.target.value })}
                    className="flex h-7 w-20 rounded-md border border-input bg-transparent px-2 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    placeholder="0.00"
                    step="0.01"
                  />
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saving && <Loader2 className="h-3 w-3 animate-spin" />}
            Save Baselines
          </button>
        </div>
      </div>
    </div>
  );
}

export function CostTab() {
  const { data: cost, isLoading, refetch } = useExecCostSummary();
  const { data: config } = useExecConfig();

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
    return <BaselinesConfigForm onSaved={() => refetch()} />;
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
            <div className="w-3 h-0.5 bg-red-600 rounded" />
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
