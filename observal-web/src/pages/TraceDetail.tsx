import { useState } from "react";
import { useQuery, useSubscription } from "urql";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Spinner } from "@/components/ui/spinner";
import { TraceTree } from "@/components/traces";
import { formatDuration, formatDate } from "@/lib/format";
import { TRACE_DETAIL_QUERY, SPAN_SUBSCRIPTION } from "@/lib/queries";

interface Span {
  spanId: string;
  parentSpanId?: string | null;
  type: string;
  name: string;
  method?: string;
  startTime: string;
  endTime?: string;
  latencyMs?: number | null;
  status: string;
  input?: string | null;
  output?: string | null;
  error?: string | null;
  tokenCountInput?: number | null;
  tokenCountOutput?: number | null;
  tokenCountTotal?: number | null;
  cost?: number | null;
  toolSchemaValid?: boolean | null;
  toolsAvailable?: string[] | null;
}

interface Score {
  scoreId: string;
  name: string;
  source: string;
  value: number;
  comment?: string;
}

const scoreColumns: Column<Score>[] = [
  { key: "name", label: "Name" },
  {
    key: "source",
    label: "Source",
    render: (row) => <Badge variant="secondary">{row.source}</Badge>,
  },
  { key: "value", label: "Value", className: "text-right", sortable: true },
];

export default function TraceDetail() {
  const { traceId } = useParams<{ traceId: string }>();
  const [selectedSpanId, setSelectedSpanId] = useState<string | undefined>();

  const [{ data, fetching }] = useQuery({
    query: TRACE_DETAIL_QUERY,
    variables: { traceId: traceId! },
    pause: !traceId,
  });

  const [sub] = useSubscription({
    query: SPAN_SUBSCRIPTION,
    variables: { traceId: traceId! },
    pause: !traceId,
  });

  const trace = data?.trace;
  const spans: Span[] = trace?.spans ?? [];
  const scores: Score[] = trace?.scores ?? [];
  const selectedSpan = spans.find((s) => s.spanId === selectedSpanId);

  if (fetching && !trace) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!trace) {
    return (
      <>
        <Link to="/traces" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4" /> Back to traces
        </Link>
        <p className="text-muted-foreground">Trace not found.</p>
      </>
    );
  }

  const totalLatency = trace.endTime && trace.startTime
    ? new Date(trace.endTime).getTime() - new Date(trace.startTime).getTime()
    : null;

  return (
    <>
      <Link to="/traces" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="h-4 w-4" /> Back to traces
      </Link>

      <PageHeader title={`Trace ${trace.traceId.slice(0, 12)}…`} />

      {sub.data && (
        <div className="mb-3 flex items-center gap-2 text-xs text-green-600">
          <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          Live
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card>
          <CardHeader><CardTitle>Type</CardTitle></CardHeader>
          <CardContent><Badge variant="secondary">{trace.traceType}</Badge></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Spans</CardTitle></CardHeader>
          <CardContent><span className="text-lg font-semibold">{spans.length}</span></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Start</CardTitle></CardHeader>
          <CardContent><span className="text-sm">{formatDate(trace.startTime)}</span></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Duration</CardTitle></CardHeader>
          <CardContent>
            <span className="text-sm">{totalLatency != null ? formatDuration(totalLatency) : "—"}</span>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <div className="lg:col-span-2">
          <div className="border rounded-lg bg-card p-4">
            <h3 className="text-sm font-medium mb-3">Span Tree</h3>
            <TraceTree spans={spans} selectedSpanId={selectedSpanId} onSelectSpan={setSelectedSpanId} />
          </div>
        </div>
        <div className="lg:col-span-1">
          <div className="sticky top-20">
            <Card className="h-full">
              <CardHeader><CardTitle>Span Detail</CardTitle></CardHeader>
              <CardContent>
                {selectedSpan ? (
                  <div className="space-y-3 text-sm">
                    <div>
                      <span className="text-muted-foreground">Name</span>
                      <p className="font-medium">{selectedSpan.name}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Status</span>
                      <p><Badge variant={selectedSpan.status === "error" ? "destructive" : "secondary"}>{selectedSpan.status}</Badge></p>
                    </div>
                    {selectedSpan.latencyMs != null && (
                      <div>
                        <span className="text-muted-foreground">Latency</span>
                        <p>{formatDuration(selectedSpan.latencyMs)}</p>
                      </div>
                    )}
                    {(selectedSpan.tokenCountInput != null || selectedSpan.tokenCountOutput != null) && (
                      <div>
                        <span className="text-muted-foreground">Tokens</span>
                        <p>{selectedSpan.tokenCountInput ?? 0} in / {selectedSpan.tokenCountOutput ?? 0} out</p>
                      </div>
                    )}
                    {selectedSpan.cost != null && (
                      <div>
                        <span className="text-muted-foreground">Cost</span>
                        <p>${selectedSpan.cost.toFixed(4)}</p>
                      </div>
                    )}
                    {selectedSpan.input && (
                      <div>
                        <span className="text-muted-foreground">Input</span>
                        <pre className="mt-1 max-h-48 overflow-auto rounded border bg-muted/50 p-2 text-xs whitespace-pre-wrap">{selectedSpan.input}</pre>
                      </div>
                    )}
                    {selectedSpan.output && (
                      <div>
                        <span className="text-muted-foreground">Output</span>
                        <pre className="mt-1 max-h-48 overflow-auto rounded border bg-muted/50 p-2 text-xs whitespace-pre-wrap">{selectedSpan.output}</pre>
                      </div>
                    )}
                    {selectedSpan.error && (
                      <div>
                        <span className="text-muted-foreground">Error</span>
                        <pre className="mt-1 max-h-48 overflow-auto rounded border border-destructive/20 bg-destructive/5 p-2 text-xs text-destructive whitespace-pre-wrap">{selectedSpan.error}</pre>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Select a span to view details.</p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {scores.length > 0 && (
        <div className="mt-4">
          <h2 className="text-sm font-medium mb-2">Scores</h2>
          <DataTable columns={scoreColumns} data={scores} />
        </div>
      )}
    </>
  );
}
