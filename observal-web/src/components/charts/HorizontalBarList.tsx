import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface BarItem {
  name: string;
  value: number;
}

export function HorizontalBarList({
  data,
  maxItems = 5,
  valueFormatter = (v: number) => String(v),
}: {
  data: BarItem[];
  maxItems?: number;
  valueFormatter?: (value: number) => string;
  color?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const maxValue = sorted[0]?.value || 1;
  const visible = expanded ? sorted.slice(0, 20) : sorted.slice(0, maxItems);
  const canExpand = sorted.length > maxItems;

  return (
    <div>
      <div
        className="space-y-1 overflow-hidden transition-all duration-300"
        style={{ maxHeight: expanded ? 20 * 36 : maxItems * 36 }}
      >
        {visible.map((item) => (
          <div
            key={item.name}
            className="relative flex h-9 items-center justify-between rounded px-2 hover:bg-muted/50"
          >
            <div
              className="absolute inset-y-0 left-0 rounded bg-primary-accent/10"
              style={{ width: `${(item.value / maxValue) * 100}%` }}
            />
            <span className="relative truncate text-sm">{item.name}</span>
            <span className="relative ml-2 shrink-0 font-mono text-sm text-muted-foreground">
              {valueFormatter(item.value)}
            </span>
          </div>
        ))}
      </div>
      {canExpand && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 flex w-full items-center justify-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          {expanded ? (
            <>Show less <ChevronUp className="h-3 w-3" /></>
          ) : (
            <>Show more <ChevronDown className="h-3 w-3" /></>
          )}
        </button>
      )}
    </div>
  );
}
