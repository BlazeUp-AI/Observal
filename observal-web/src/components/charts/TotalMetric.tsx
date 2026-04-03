import type { ReactNode } from "react";

export function TotalMetric({
  metric,
  description,
}: {
  metric: ReactNode;
  description?: ReactNode;
}) {
  return (
    <div className="mb-3">
      <span className="text-2xl font-semibold tabular-nums">{metric}</span>
      {description && <span className="ml-1.5 text-sm text-muted-foreground">{description}</span>}
    </div>
  );
}
