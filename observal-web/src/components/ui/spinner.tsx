import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const sizes = { sm: "h-4 w-4", default: "h-5 w-5", lg: "h-8 w-8" };

export function Spinner({
  size = "default",
  className,
}: {
  size?: "sm" | "default" | "lg";
  className?: string;
}) {
  return <Loader2 className={cn("animate-spin text-muted-foreground", sizes[size], className)} />;
}
