import { useState } from "react";
import { useQuery } from "urql";
import { useNavigate } from "react-router-dom";
import { Link } from "react-router-dom";
import { RotateCw } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDuration, formatRelativeTime } from "@/lib/format";
import { TRACES_QUERY } from "@/lib/queries";

interface Trace {
  traceId: string;
  traceType: string;
  name: string;
  startTime: string;
  metrics: {
    totalSpans: number;
    errorCount: number;
    totalLatencyMs: number;
  };
}

const columns: Column<Trace>[] = [
  {
    key: "traceId",
    label: "Trace ID",
    render: (row) => (
      <Link to={`/traces/${row.traceId}`} className="font-mono text-xs text-primary hover:underline">
        {row.traceId.slice(0, 12)}
      </Link>
    ),
  },
  {
    key: "traceType",
    label: "Type",
    render: (row) => <Badge variant="secondary">{row.traceType}</Badge>,
  },
  { key: "name", label: "Name" },
  {
    key: "totalSpans",
    label: "Spans",
    className: "text-right",
    sortable: true,
    render: (row) => row.metrics.totalSpans,
  },
  {
    key: "errorCount",
    label: "Errors",
    sortable: true,
    render: (row) =>
      row.metrics.errorCount > 0 ? (
        <Badge variant="destructive">{row.metrics.errorCount}</Badge>
      ) : (
        <span className="text-muted-foreground">0</span>
      ),
  },
  {
    key: "totalLatencyMs",
    label: "Latency",
    sortable: true,
    render: (row) => formatDuration(row.metrics.totalLatencyMs),
  },
  {
    key: "startTime",
    label: "Time",
    sortable: true,
    render: (row) => (
      <span className="text-muted-foreground">{formatRelativeTime(row.startTime)}</span>
    ),
  },
];

export default function Traces() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  const [{ data, fetching }, reexecute] = useQuery({
    query: TRACES_QUERY,
    variables: {
      traceType: typeFilter === "all" ? undefined : typeFilter,
      limit: 100,
    },
  });

  const items: Trace[] = data?.traces?.items ?? [];
  const filtered = search
    ? items.filter(
        (t) =>
          t.name?.toLowerCase().includes(search.toLowerCase()) ||
          t.traceId.toLowerCase().includes(search.toLowerCase())
      )
    : items;

  return (
    <>
      <PageHeader title="Tracing" />

      <div className="border-b pb-3 mb-0">
        <div className="flex items-center gap-2">
          <Input
            placeholder="Search traces..."
            className="w-64 h-8 text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="h-8 rounded-md border border-input bg-background px-3 text-sm"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="all">All types</option>
            <option value="mcp">MCP</option>
            <option value="agent">Agent</option>
          </select>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => reexecute({ requestPolicy: "network-only" })}
          >
            <RotateCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="pt-3">
        {!fetching && filtered.length === 0 ? (
          <EmptyState title="No traces found" description="Traces will appear here once telemetry data is ingested." />
        ) : (
          <DataTable
            columns={columns}
            data={filtered}
            isLoading={fetching}
            onRowClick={(row) => navigate(`/traces/${row.traceId}`)}
            emptyMessage="No traces"
          />
        )}
      </div>
    </>
  );
}
