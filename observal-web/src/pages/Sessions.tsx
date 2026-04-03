import { useMemo } from "react";
import { useQuery } from "urql";
import { useNavigate } from "react-router-dom";
import { TRACES_QUERY } from "@/lib/queries";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/data-table";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatRelativeTime } from "@/lib/format";
import { Clock } from "lucide-react";

interface SessionRow {
  sessionId: string;
  traceCount: number;
  firstSeen: string;
  lastActive: string;
}

export function Sessions() {
  const [result] = useQuery({ query: TRACES_QUERY, variables: { limit: 500 } });
  const navigate = useNavigate();

  const sessions = useMemo<SessionRow[]>(() => {
    const items = result.data?.traces?.items ?? [];
    const map = new Map<string, { count: number; first: string; last: string }>();
    for (const t of items) {
      if (!t.sessionId) continue;
      const existing = map.get(t.sessionId);
      if (existing) {
        existing.count++;
        if (t.startTime < existing.first) existing.first = t.startTime;
        if (t.startTime > existing.last) existing.last = t.startTime;
      } else {
        map.set(t.sessionId, { count: 1, first: t.startTime, last: t.startTime });
      }
    }
    return Array.from(map.entries())
      .map(([id, v]) => ({ sessionId: id, traceCount: v.count, firstSeen: v.first, lastActive: v.last }))
      .sort((a, b) => b.lastActive.localeCompare(a.lastActive));
  }, [result.data]);

  if (result.fetching) return <div className="flex h-64 items-center justify-center"><Spinner /></div>;
  if (result.error) return <p className="text-destructive">Error: {result.error.message}</p>;

  return (
    <div>
      <PageHeader title="Sessions" description="Traces grouped by session_id" />
      {sessions.length === 0 ? (
        <EmptyState
          icon={<Clock className="h-8 w-8" />}
          title="No sessions yet"
          description="Sessions are created when traces include a session_id."
        />
      ) : (
        <DataTable
          columns={[
            { key: "sessionId", label: "Session ID", className: "font-mono", render: (r: SessionRow) => r.sessionId.slice(0, 12) + "…" },
            { key: "traceCount", label: "Traces", sortable: true },
            { key: "firstSeen", label: "First Seen", render: (r: SessionRow) => formatRelativeTime(r.firstSeen), sortable: true },
            { key: "lastActive", label: "Last Active", render: (r: SessionRow) => formatRelativeTime(r.lastActive), sortable: true },
          ]}
          data={sessions}
          onRowClick={(r: SessionRow) => navigate(`/traces?session=${r.sessionId}`)}
        />
      )}
    </div>
  );
}

export default Sessions;
