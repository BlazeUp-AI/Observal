"use client";

import { use } from "react";
import { useOtelSession } from "@/hooks/use-api";
import Link from "next/link";

export default function TraceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading } = useOtelSession(id);

  if (isLoading) return <div className="p-6 text-muted-foreground">Loading...</div>;
  if (!data) return <div className="p-6 text-muted-foreground">Trace not found</div>;

  const session = data as any;
  const events = session.events ?? [];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/traces" className="text-sm text-muted-foreground hover:text-foreground">Traces</Link>
        <span className="text-muted-foreground">/</span>
        <h1 className="text-lg font-semibold font-mono">{id.slice(0, 16)}...</h1>
      </div>

      {session.service_name && (
        <p className="text-sm text-muted-foreground">Service: {session.service_name}</p>
      )}

      <div className="space-y-2">
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No events in this trace</p>
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
    </div>
  );
}
