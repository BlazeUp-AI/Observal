import { cn } from "@/lib/utils";

type StatusConfig = { dot: string; bg?: string; ping: boolean };

const statusMap: Record<string, StatusConfig> = {
  active:    { dot: "bg-dark-green", bg: "bg-light-green", ping: true },
  approved:  { dot: "bg-dark-green", bg: "bg-light-green", ping: true },
  success:   { dot: "bg-dark-green", bg: "bg-light-green", ping: true },
  pending:   { dot: "bg-dark-yellow", bg: "bg-light-yellow", ping: true },
  queued:    { dot: "bg-dark-yellow", bg: "bg-light-yellow", ping: true },
  error:     { dot: "bg-dark-red", ping: false },
  failed:    { dot: "bg-dark-red", ping: false },
  rejected:  { dot: "bg-dark-red", ping: false },
  completed: { dot: "bg-dark-green", ping: false },
  done:      { dot: "bg-dark-green", ping: false },
  inactive:  { dot: "bg-muted-foreground", ping: false },
  paused:    { dot: "bg-muted-foreground", ping: false },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const config = statusMap[status.toLowerCase()] ?? { dot: "bg-muted-foreground", ping: false };

  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs", className)}>
      <span className="relative flex h-2 w-2">
        {config.ping && (
          <span className={cn("absolute inset-0 animate-ping rounded-full opacity-75", config.dot)} />
        )}
        <span className={cn("relative h-2 w-2 rounded-full", config.dot)} />
      </span>
      {status}
    </span>
  );
}
