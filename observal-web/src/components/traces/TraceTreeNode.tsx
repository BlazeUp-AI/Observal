import { cn } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import { SpanContent } from "./SpanContent";
import type { TreeNode } from "./TraceTree";

const TYPE_STYLES: Record<string, { bg: string; letter: string }> = {
  tool_call:  { bg: "bg-blue-100 text-blue-700", letter: "T" },
  tool_list:  { bg: "bg-blue-100 text-blue-700", letter: "T" },
  generation: { bg: "bg-purple-100 text-purple-700", letter: "G" },
  retriever:  { bg: "bg-green-100 text-green-700", letter: "R" },
  agent:      { bg: "bg-orange-100 text-orange-700", letter: "A" },
  hook:       { bg: "bg-yellow-100 text-yellow-700", letter: "H" },
  embedding:  { bg: "bg-cyan-100 text-cyan-700", letter: "E" },
  sandbox:    { bg: "bg-rose-100 text-rose-700", letter: "S" },
};

function getTypeStyle(type: string) {
  return TYPE_STYLES[type] ?? { bg: "bg-gray-100 text-gray-600", letter: "S" };
}

export function TraceTreeNode({
  node, depth, isLast, isSelected, isCollapsed, onToggle, onSelect, parentLines,
}: {
  node: TreeNode;
  depth: number;
  isLast: boolean;
  isSelected: boolean;
  isCollapsed: boolean;
  onToggle: (id: string) => void;
  onSelect: (id: string) => void;
  parentLines: boolean[];
}) {
  const style = getTypeStyle(node.span.type);
  const hasChildren = node.children.length > 0;

  return (
    <div
      className={cn(
        "flex items-start py-1 px-2 rounded-md cursor-pointer hover:bg-muted/30",
        isSelected && "bg-primary/5 border-l-2 border-primary",
      )}
      style={{ paddingLeft: depth * 24 + 8 }}
      onClick={() => onSelect(node.span.spanId)}
    >
      {/* Tree connector lines */}
      <div className="relative mr-2 flex-shrink-0 self-stretch" style={{ width: 20 }}>
        {depth > 0 && (
          <>
            {/* vertical line to midpoint */}
            <div className="absolute left-[9px] top-0 h-1/2 w-px bg-border" />
            {/* horizontal line to icon */}
            <div className="absolute left-[9px] top-1/2 h-px w-[11px] bg-border" />
            {/* continue vertical line down if not last */}
            {!isLast && <div className="absolute left-[9px] top-1/2 h-1/2 w-px bg-border" />}
          </>
        )}
      </div>

      {/* Ancestor vertical lines */}
      {parentLines.map((active, i) =>
        active ? (
          <div key={i} className="absolute w-px bg-border" style={{ left: i * 24 + 8 + 9, top: 0, bottom: 0 }} />
        ) : null,
      )}

      {/* Type icon */}
      <div className={cn("flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold mt-0.5", style.bg)}>
        {style.letter}
      </div>

      {/* Collapse toggle */}
      {hasChildren && (
        <button
          className="ml-1 mt-0.5 flex-shrink-0 text-muted-foreground hover:text-foreground"
          onClick={(e) => { e.stopPropagation(); onToggle(node.span.spanId); }}
        >
          <ChevronRight className={cn("h-4 w-4 transition-transform duration-150", !isCollapsed && "rotate-90")} />
        </button>
      )}

      {/* Content */}
      <div className={cn("ml-2 min-w-0 flex-1", !hasChildren && "ml-7")}>
        <SpanContent span={node.span} isSelected={isSelected} />
      </div>
    </div>
  );
}
