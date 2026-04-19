import { Badge } from "@/components/ui/badge";

const PLATFORM_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  "Claude Code": {
    bg: "bg-blue-500/8 dark:bg-blue-500/15",
    text: "text-blue-700 dark:text-blue-300",
    dot: "bg-blue-500",
  },
  Kiro: {
    bg: "bg-orange-500/8 dark:bg-orange-500/15",
    text: "text-orange-700 dark:text-orange-300",
    dot: "bg-orange-500",
  },
};

const DEFAULT_STYLE = {
  bg: "bg-muted/50",
  text: "text-muted-foreground",
  dot: "bg-muted-foreground/40",
};

export function PlatformBadge({ platform }: { platform?: string }) {
  const label = platform || "Unknown";
  const style = PLATFORM_STYLES[label] ?? DEFAULT_STYLE;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium ${style.bg} ${style.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {label}
    </span>
  );
}
