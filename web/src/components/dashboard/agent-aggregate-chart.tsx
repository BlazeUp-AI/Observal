"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";

import type { AgentAggregate } from "@/lib/types";

interface AgentAggregateChartProps {
  data: AgentAggregate;
}

export function AgentAggregateChart({ data }: AgentAggregateChartProps) {
  const chartData = data.trend.map((t) => ({
    timestamp: new Date(t.timestamp).toLocaleDateString(),
    composite: t.composite,
    ci_low: data.ci_low,
    ci_high: data.ci_high,
  }));

  if (chartData.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 text-sm">
        <span>
          Mean: <strong>{data.mean.toFixed(1)}</strong>/100
        </span>
        <span>
          CI: [{data.ci_low.toFixed(1)}, {data.ci_high.toFixed(1)}]
        </span>
        {data.drift_alert && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
            Drift Detected
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="timestamp" tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Tooltip />
          <ReferenceLine y={data.ci_low} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 4" />
          <ReferenceLine y={data.ci_high} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 4" />
          <Area
            type="monotone"
            dataKey="composite"
            stroke="hsl(var(--primary))"
            fill="hsl(var(--primary))"
            fillOpacity={0.2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DriftBadge({ driftAlert }: { driftAlert: boolean }) {
  if (!driftAlert) return null;
  return (
    <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
      Drift
    </span>
  );
}
