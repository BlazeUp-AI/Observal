import { PageHeader } from "@/components/layout/PageHeader";
import { useParams, Link } from "react-router-dom";
import { useApiQuery } from "@/lib/api";
import { formatNumber, formatDuration } from "@/lib/format";
import { Card, Badge, Spinner } from "@/components/ui";
import { StatCard } from "@/components/ui/stat-card";
import { ChartCard, BarChart } from "@/components/charts";
import { ArrowLeft, Download, Zap, AlertTriangle, Clock } from "lucide-react";

export default function McpDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: mcp, loading } = useApiQuery<any>(`/api/v1/mcps/${id}`);
  const { data: metrics, loading: mLoading } = useApiQuery<any>(`/api/v1/dashboard/mcp/${id}/metrics`);

  if (loading) return <div className="flex h-64 items-center justify-center"><Spinner /></div>;
  if (!mcp) return <p className="text-muted-foreground">MCP server not found.</p>;

  const latencyData = metrics ? [
    { name: "p50", ms: metrics.p50_latency_ms ?? 0 },
    { name: "p90", ms: metrics.p90_latency_ms ?? 0 },
    { name: "p99", ms: metrics.p99_latency_ms ?? 0 },
  ] : [];

  return (
    <div>
      <Link to="/mcps" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back to MCP Servers
      </Link>
      <PageHeader title={mcp.name} description={mcp.version ? `v${mcp.version}` : undefined} />

      <Card className="mb-6 p-5 space-y-3 text-sm">
        {mcp.description && <p>{mcp.description}</p>}
        {mcp.git_url && <p>Git: <a href={mcp.git_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">{mcp.git_url}</a></p>}
        {mcp.owner && <p className="text-muted-foreground">Owner: {mcp.owner}</p>}
        {mcp.category && <p>Category: <Badge variant="outline">{mcp.category}</Badge></p>}
        {mcp.supported_ides?.length > 0 && (
          <div className="flex items-center gap-1 flex-wrap">
            IDEs: {mcp.supported_ides.map((ide: string) => <Badge key={ide} variant="outline">{ide}</Badge>)}
          </div>
        )}
        {mcp.setup_instructions && <p className="text-muted-foreground whitespace-pre-wrap">{mcp.setup_instructions}</p>}
      </Card>

      {metrics && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
            <StatCard title="Downloads" value={formatNumber(metrics.downloads ?? 0)} icon={<Download className="h-4 w-4" />} />
            <StatCard title="Tool Calls" value={formatNumber(metrics.tool_calls ?? 0)} icon={<Zap className="h-4 w-4" />} />
            <StatCard title="Error Rate" value={`${((metrics.error_rate ?? 0) * 100).toFixed(1)}%`} icon={<AlertTriangle className="h-4 w-4" />} />
            <StatCard title="Avg Latency" value={formatDuration(metrics.avg_latency_ms ?? 0)} icon={<Clock className="h-4 w-4" />} />
          </div>
          {latencyData.some((d) => d.ms > 0) && (
            <ChartCard title="Latency Percentiles" isLoading={mLoading}>
              <BarChart data={latencyData} bars={[{ key: "ms", label: "Latency", color: "#3b82f6" }]} valueFormatter={(v) => `${v}ms`} />
            </ChartCard>
          )}
        </>
      )}
    </div>
  );
}
