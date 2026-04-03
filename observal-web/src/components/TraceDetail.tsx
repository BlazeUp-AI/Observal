import { useParams } from 'react-router-dom';
import { useQuery, useSubscription } from 'urql';
import { TRACE_DETAIL_QUERY, SPAN_SUBSCRIPTION } from '../lib/queries';

export function TraceDetail() {
  const { traceId } = useParams<{ traceId: string }>();
  const [result] = useQuery({ query: TRACE_DETAIL_QUERY, variables: { traceId } });
  const [subResult] = useSubscription({ query: SPAN_SUBSCRIPTION, variables: { traceId } });

  const { data, fetching, error } = result;

  if (fetching) return <p>Loading…</p>;
  if (error) return <p>Error: {error.message}</p>;

  const trace = data?.trace;
  if (!trace) return <p>Trace not found.</p>;

  return (
    <div>
      <h2>Trace: {trace.traceId.slice(0, 8)}…</h2>
      <dl>
        <dt>Type</dt><dd>{trace.traceType}</dd>
        <dt>Name</dt><dd>{trace.name || '—'}</dd>
        <dt>Start</dt><dd>{trace.startTime}</dd>
        <dt>End</dt><dd>{trace.endTime || 'ongoing'}</dd>
      </dl>

      <h3>Spans ({trace.spans.length})</h3>
      <table>
        <thead>
          <tr><th>Type</th><th>Name</th><th>Status</th><th>Latency</th><th>Schema</th></tr>
        </thead>
        <tbody>
          {trace.spans.map((s: any) => (
            <tr key={s.spanId} style={{ color: s.status === 'error' ? 'red' : undefined }}>
              <td>{s.type}</td>
              <td>{s.name}</td>
              <td>{s.status}</td>
              <td>{s.latencyMs ? `${s.latencyMs}ms` : '—'}</td>
              <td>{s.toolSchemaValid === true ? '✓' : s.toolSchemaValid === false ? '✗' : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {trace.scores.length > 0 && (
        <>
          <h3>Scores</h3>
          <table>
            <thead><tr><th>Name</th><th>Source</th><th>Value</th></tr></thead>
            <tbody>
              {trace.scores.map((sc: any) => (
                <tr key={sc.scoreId}><td>{sc.name}</td><td>{sc.source}</td><td>{sc.value}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {subResult.data && (
        <p>Live: new span — {subResult.data.spanCreated.name} ({subResult.data.spanCreated.status})</p>
      )}
    </div>
  );
}
