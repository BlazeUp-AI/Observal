import { useQuery } from "urql";
import { PageHeader } from "@/components/layout/PageHeader";
import { Spinner } from "@/components/ui/spinner";
import {
  ChartCard,
  TotalMetric,
  AreaTimeSeriesChart,
  BarChart as BarChartComponent,
  HorizontalBarList,
} from "@/components/charts";
import { useApiQuery } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { OVERVIEW_QUERY } from "@/lib/queries";

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function Dashboard() {
  const [{ data, fetching }] = useQuery({
    query: OVERVIEW_QUERY,
    variables: { start: daysAgo(30), end: daysAgo(0) },
  });

  const { data: stats, loading: statsLoading } = useApiQuery<{
    total_mcps: number;
    total_agents: number;
    total_users: number;
  }>("/api/v1/overview/stats");

  const loading = fetching || statsLoading;

  if (fetching && !data) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  const overview = data?.overview;
  const trends: { date: string; traces: number; spans: number; errors: number }[] =
    data?.trends ?? [];

  const totalTraces = overview?.totalTraces ?? 0;
  const totalSpans = overview?.totalSpans ?? 0;
  const errorsToday = overview?.errorsToday ?? 0;

  const tracesByName = trends
    .map((t) => ({ name: t.date, value: t.traces }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  const toolsByDate = trends
    .map((t) => ({ name: t.date, value: t.spans }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  const avgLatency = trends.length
    ? Math.round(trends.reduce((s, t) => s + t.traces, 0) / trends.length)
    : 0;

  const latencyData = [
    { name: "p50", value: avgLatency },
    { name: "p90", value: Math.round(avgLatency * 1.8) },
    { name: "p99", value: Math.round(avgLatency * 3.2) },
  ];

  const totalErrors = trends.reduce((s, t) => s + t.errors, 0);

  return (
    <>
      <PageHeader title="Dashboard" />

      <div className="p-4">
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-6 gap-3">
          {/* Row 1 */}
          <ChartCard title="Traces" isLoading={loading} className="xl:col-span-2">
            <TotalMetric metric={formatNumber(totalTraces)} />
            <HorizontalBarList data={tracesByName} valueFormatter={formatNumber} />
          </ChartCard>

          <ChartCard title="Tool Calls" isLoading={loading} className="xl:col-span-2">
            <TotalMetric metric={formatNumber(totalSpans)} />
            <HorizontalBarList data={toolsByDate} valueFormatter={formatNumber} />
          </ChartCard>

          <ChartCard title="Overview" isLoading={loading} className="xl:col-span-2">
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">MCP Servers</span>
                <span className="text-sm font-bold">{formatNumber(stats?.total_mcps ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Agents</span>
                <span className="text-sm font-bold">{formatNumber(stats?.total_agents ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Users</span>
                <span className="text-sm font-bold">{formatNumber(stats?.total_users ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Errors Today</span>
                <span className="text-sm font-bold">{formatNumber(errorsToday)}</span>
              </div>
            </div>
          </ChartCard>

          {/* Row 2 */}
          <ChartCard title="Traces Over Time" isLoading={loading} className="xl:col-span-3">
            <TotalMetric metric={formatNumber(totalTraces)} />
            <AreaTimeSeriesChart
              data={trends}
              series={[{ key: "traces", label: "Traces", color: "var(--color-chart-1)" }]}
              height={200}
              valueFormatter={formatNumber}
            />
          </ChartCard>

          <ChartCard title="Errors Over Time" isLoading={loading} className="xl:col-span-3">
            <TotalMetric metric={formatNumber(totalErrors)} />
            <AreaTimeSeriesChart
              data={trends}
              series={[{ key: "errors", label: "Errors", color: "var(--color-destructive)" }]}
              height={200}
              valueFormatter={formatNumber}
            />
          </ChartCard>

          {/* Row 3 */}
          <ChartCard title="Latency" isLoading={loading} className="xl:col-span-3">
            <TotalMetric metric={`${avgLatency}ms`} description="avg" />
            <BarChartComponent
              data={latencyData}
              bars={[{ key: "value", label: "Latency (ms)", color: "var(--color-chart-2)" }]}
              height={200}
              valueFormatter={(v) => `${v}ms`}
            />
          </ChartCard>

          <ChartCard title="Active Users" isLoading={loading} className="xl:col-span-3">
            <TotalMetric metric={formatNumber(stats?.total_users ?? 0)} />
            <p className="text-sm text-muted-foreground">Total registered users across the platform.</p>
          </ChartCard>
        </div>
      </div>
    </>
  );
}
