import { useState, useMemo, useCallback } from "react";
import { TraceTreeNode } from "./TraceTreeNode";

export interface Span {
  spanId: string;
  parentSpanId?: string | null;
  type: string;
  name: string;
  status: string;
  latencyMs?: number | null;
  startTime: string;
  tokenCountInput?: number | null;
  tokenCountOutput?: number | null;
  cost?: number | null;
  toolSchemaValid?: boolean | null;
  input?: string | null;
  output?: string | null;
  error?: string | null;
}

export interface TreeNode {
  span: Span;
  children: TreeNode[];
}

function buildTree(spans: Span[]): TreeNode[] {
  const map = new Map<string, TreeNode>();
  for (const span of spans) map.set(span.spanId, { span, children: [] });

  const roots: TreeNode[] = [];
  for (const span of spans) {
    const node = map.get(span.spanId)!;
    const parent = span.parentSpanId ? map.get(span.parentSpanId) : undefined;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }

  const sort = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.span.startTime.localeCompare(b.span.startTime));
    nodes.forEach((n) => sort(n.children));
  };
  sort(roots);
  return roots;
}

export function TraceTree({
  spans, selectedSpanId, onSelectSpan,
}: {
  spans: Span[];
  selectedSpanId?: string;
  onSelectSpan?: (spanId: string) => void;
}) {
  const tree = useMemo(() => buildTree(spans), [spans]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggle = useCallback((id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const select = useCallback((id: string) => onSelectSpan?.(id), [onSelectSpan]);

  function renderNodes(nodes: TreeNode[], depth: number, parentLines: boolean[]) {
    return nodes.map((node, i) => {
      const isLast = i === nodes.length - 1;
      const isCollapsed = collapsed.has(node.span.spanId);
      const nextParentLines = [...parentLines, !isLast];

      return (
        <div key={node.span.spanId} className="relative">
          <TraceTreeNode
            node={node}
            depth={depth}
            isLast={isLast}
            isSelected={selectedSpanId === node.span.spanId}
            isCollapsed={isCollapsed}
            onToggle={toggle}
            onSelect={select}
            parentLines={parentLines}
          />
          {!isCollapsed && node.children.length > 0 && renderNodes(node.children, depth + 1, nextParentLines)}
        </div>
      );
    });
  }

  return <div className="space-y-0.5">{renderNodes(tree, 0, [])}</div>;
}
