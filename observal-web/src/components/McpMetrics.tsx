import { useQuery } from 'urql';
import { MCP_METRICS_QUERY } from '../lib/queries';
import { useParams } from 'react-router-dom';

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 19).replace('T', ' ');
}

export function McpMetrics() {
  const { mcpId } = useParams<{ mcpId: string }>();
  const [result] = useQuery({
    query: MCP_METRICS_QUERY,
    variables: { mcpId, start: daysAgo(30), end: daysAgo(0) },
  });
  const { data, fetching, error } = result;

  if (fetching) return <p>Loading…</p>;
  if (error) return <p>Error: {error.message}</p>;

  const m = data?.mcpMetrics;
  if (!m) return <p>No metrics.</p>;

  return (
    <div>
      <h2>MCP Metrics</h2>
      <dl>
        <dt>Tool Calls</dt><dd>{m.toolCallCount}</dd>
        <dt>Error Rate</dt><dd>{(m.errorRate * 100).toFixed(1)}%</dd>
        <dt>Avg Latency</dt><dd>{m.avgLatencyMs.toFixed(1)}ms</dd>
        <dt>p50</dt><dd>{m.p50LatencyMs.toFixed(0)}ms</dd>
        <dt>p90</dt><dd>{m.p90LatencyMs.toFixed(0)}ms</dd>
        <dt>p99</dt><dd>{m.p99LatencyMs.toFixed(0)}ms</dd>
        <dt>Timeout Rate</dt><dd>{(m.timeoutRate * 100).toFixed(1)}%</dd>
        <dt>Schema Compliance</dt><dd>{(m.schemaComplianceRate * 100).toFixed(1)}%</dd>
      </dl>
    </div>
  );
}
