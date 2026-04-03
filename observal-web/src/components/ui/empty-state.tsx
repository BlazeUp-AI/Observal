import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function EmptyState({
  icon,
  title,
  description,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-16", className)}>
      {icon && <div className="text-muted-foreground/50 mb-3">{icon}</div>}
      <p className="text-base font-medium">{title}</p>
      {description && (
        <p className="text-sm text-muted-foreground mt-1 max-w-sm text-center">{description}</p>
      )}
    </div>
  );
}
