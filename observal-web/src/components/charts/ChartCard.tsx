import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export function ChartCard({
  title,
  description,
  isLoading,
  headerRight,
  children,
  className,
  contentClassName,
}: {
  title: ReactNode;
  description?: ReactNode;
  isLoading: boolean;
  headerRight?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <Card className={cn("min-h-[200px]", className)}>
      <CardHeader className="relative">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>{title}</CardTitle>
            {description && (
              <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
            )}
          </div>
          {headerRight}
        </div>
        {isLoading && (
          <Loader2 className="absolute right-4 top-4 h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </CardHeader>
      <CardContent className={contentClassName}>{children}</CardContent>
    </Card>
  );
}
