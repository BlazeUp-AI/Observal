import { cn } from "@/lib/utils";
import { Card, CardContent } from "./card";
import type { ReactNode } from "react";

export function StatCard({
  title,
  value,
  change,
  icon,
  className,
}: {
  title: string;
  value: string | number;
  change?: number;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-muted-foreground">{title}</span>
          {icon && <span className="text-muted-foreground/50">{icon}</span>}
        </div>
        <div className="text-2xl font-bold mt-1">{value}</div>
        {change !== undefined && (
          <span className={cn("text-xs", change >= 0 ? "text-dark-green" : "text-dark-red")}>
            {change >= 0 ? "+" : ""}{change}%
          </span>
        )}
      </CardContent>
    </Card>
  );
}
