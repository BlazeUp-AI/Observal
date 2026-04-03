import { useQuery } from 'urql';
import { TRACES_QUERY } from '../lib/queries';
import { Link } from 'react-router-dom';

export function TraceExplorer() {
  const [result] = useQuery({ query: TRACES_QUERY, variables: { limit: 50 } });
  const { data, fetching, error } = result;

  if (fetching) return <p>Loading traces…</p>;
  if (error) return <p>Error: {error.message}</p>;

  const traces = data?.traces?.items ?? [];

  return (
    <div>
      <h2>Trace Explorer</h2>
      <table>
        <thead>
          <tr>
            <th>Trace ID</th>
            <th>Type</th>
            <th>Name</th>
            <th>Spans</th>
            <th>Errors</th>
            <th>Latency</th>
            <th>Start</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((t: any) => (
            <tr key={t.traceId}>
              <td><Link to={`/traces/${t.traceId}`}>{t.traceId.slice(0, 8)}…</Link></td>
              <td>{t.traceType}</td>
              <td>{t.name || '—'}</td>
              <td>{t.metrics.totalSpans}</td>
              <td>{t.metrics.errorCount}</td>
              <td>{t.metrics.totalLatencyMs ? `${t.metrics.totalLatencyMs}ms` : '—'}</td>
              <td>{t.startTime}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {traces.length === 0 && <p>No traces yet.</p>}
    </div>
  );
}
