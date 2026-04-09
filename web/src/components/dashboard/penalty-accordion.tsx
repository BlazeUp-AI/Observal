"use client";

import type { TracePenalty } from "@/lib/types";

interface PenaltyAccordionProps {
  penalties: TracePenalty[];
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "text-red-500",
  moderate: "text-yellow-500",
  minor: "text-muted-foreground",
};

export function PenaltyAccordion({ penalties }: PenaltyAccordionProps) {
  if (penalties.length === 0) {
    return <p className="text-sm text-muted-foreground">No penalties applied.</p>;
  }

  return (
    <div className="space-y-2">
      {penalties.map((p, i) => (
        <details key={i} className="rounded-md border p-3">
          <summary className="flex cursor-pointer items-center justify-between text-sm font-medium">
            <span className={SEVERITY_COLORS[p.severity || "minor"] || ""}>
              {p.event_name}
            </span>
            <span className="text-muted-foreground">{p.amount}</span>
          </summary>
          <div className="mt-2 text-sm text-muted-foreground">
            <p>
              <span className="font-medium">Dimension:</span> {p.dimension}
            </p>
            <p className="mt-1">
              <span className="font-medium">Evidence:</span> {p.evidence}
            </p>
          </div>
        </details>
      ))}
    </div>
  );
}
