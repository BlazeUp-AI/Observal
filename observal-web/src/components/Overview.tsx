import { useQuery } from 'urql';
import { OVERVIEW_QUERY } from '../lib/queries';

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 19).replace('T', ' ');
}

export function Overview() {
  const now = daysAgo(0);
  const start = daysAgo(30);
  const [result] = useQuery({ query: OVERVIEW_QUERY, variables: { start, end: now } });
  const { data, fetching, error } = result;

  if (fetching) return <p>Loading…</p>;
  if (error) return <p>Error: {error.message}</p>;

  const stats = data?.overview;
  const trends = data?.trends ?? [];

  return (
    <div>
      <h2>Overview</h2>
      {stats && (
        <div style={{ display: 'flex', gap: '2rem' }}>
          <div><strong>{stats.totalTraces}</strong><br />Traces</div>
          <div><strong>{stats.totalSpans}</strong><br />Spans</div>
          <div><strong>{stats.toolCallsToday}</strong><br />Tool Calls Today</div>
          <div><strong>{stats.errorsToday}</strong><br />Errors Today</div>
        </div>
      )}

      {trends.length > 0 && (
        <>
          <h3>Trends (30d)</h3>
          <table>
            <thead><tr><th>Date</th><th>Traces</th><th>Spans</th><th>Errors</th></tr></thead>
            <tbody>
              {trends.map((t: any) => (
                <tr key={t.date}><td>{t.date}</td><td>{t.traces}</td><td>{t.spans}</td><td>{t.errors}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
