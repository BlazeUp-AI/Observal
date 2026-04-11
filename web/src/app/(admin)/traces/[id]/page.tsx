"use client";

import { use } from "react";
import { useOtelSession } from "@/hooks/use-api";
import { FileText } from "lucide-react";
import { PageHeader } from "@/components/layouts/page-header";
import { DetailSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

export default function TraceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading, isError, error, refetch } = useOtelSession(id);

  const session = data as any;
  const events = session?.events ?? [];

  return (
    <>
      <PageHeader
        title={isLoading ? "Trace" : id.slice(0, 16) + "..."}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Traces", href: "/traces" },
          { label: id.slice(0, 12) + "..." },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-4">
        {isLoading ? (
          <DetailSkeleton />
        ) : isError ? (
          <ErrorState message={error?.message} onRetry={() => refetch()} />
        ) : !data ? (
          <ErrorState message="Trace not found" />
        ) : (
          <>
            {session.service_name && (
              <p className="text-sm text-muted-foreground">Service: {session.service_name}</p>
            )}

            <div className="space-y-2">
              {events.length === 0 ? (
                <EmptyState
                  icon={FileText}
                  title="No events in this trace"
                  description="Events will appear here once spans are recorded for this session."
                />
              ) : (
                events.map((evt: any, i: number) => (
                  <div key={i} className="border border-border rounded-sm p-3 text-sm">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                      <span>{evt.event_name}</span>
                      {evt.timestamp && <span>{new Date(evt.timestamp).toLocaleTimeString()}</span>}
                    </div>
                    {evt.body && <pre className="text-xs font-mono whitespace-pre-wrap mt-1">{evt.body}</pre>}
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
