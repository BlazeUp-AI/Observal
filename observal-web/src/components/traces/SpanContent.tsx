import { useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui";
import { Clock, Hash, Coins, CheckCircle2, XCircle, Minus, ChevronDown } from "lucide-react";
import type { Span } from "./TraceTree";

function CollapsiblePre({ label, content, variant }: { label: string; content: string; variant?: "error" }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <ChevronDown className={cn("h-3 w-3 transition-transform duration-150", !open && "-rotate-90")} />
        {label}
      </button>
      {open && (
        <pre className={cn("mt-1 max-h-48 overflow-auto rounded bg-muted/30 p-2 text-xs font-mono whitespace-pre-wrap", variant === "error" && "text-destructive")}>
          {content}
        </pre>
      )}
    </div>
  );
}

export function SpanContent({ span, isSelected }: { span: Span; isSelected: boolean }) {
  const statusVariant = span.status === "success" ? "success" : span.status === "error" ? "destructive" : "outline";
  const totalTokens = (span.tokenCountInput ?? 0) + (span.tokenCountOutput ?? 0);
  const hasTokens = span.tokenCountInput != null || span.tokenCountOutput != null;

  return (
    <div className="min-w-0 flex-1">
      <div className="flex items-center gap-2">
        <span className="truncate text-sm font-medium">{span.name}</span>
        <Badge variant={statusVariant}>{span.status}</Badge>
        {span.latencyMs != null && (
          <span className="flex items-center gap-0.5 text-xs font-mono text-muted-foreground">
            <Clock className="h-3 w-3" />{span.latencyMs}ms
          </span>
        )}
      </div>

      {(isSelected || hasTokens) && (
        <div className="mt-1 flex flex-wrap items-center gap-2">
          {hasTokens && (
            <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
              <Hash className="h-3 w-3" />
              {span.tokenCountInput ?? 0}→{span.tokenCountOutput ?? 0} ({totalTokens})
            </span>
          )}
          {span.cost != null && (
            <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
              <Coins className="h-3 w-3" />${span.cost.toFixed(4)}
            </span>
          )}
          {span.toolSchemaValid === true && <CheckCircle2 className="h-3.5 w-3.5 text-success" />}
          {span.toolSchemaValid === false && <XCircle className="h-3.5 w-3.5 text-destructive" />}
          {span.toolSchemaValid == null && <Minus className="h-3.5 w-3.5 text-muted-foreground" />}
        </div>
      )}

      {isSelected && (
        <div className="mt-2 space-y-1">
          {span.input && <CollapsiblePre label="Input" content={span.input} />}
          {span.output && <CollapsiblePre label="Output" content={span.output} />}
          {span.error && <CollapsiblePre label="Error" content={span.error} variant="error" />}
        </div>
      )}
    </div>
  );
}
