import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "border-input bg-background placeholder:text-muted-foreground disabled:bg-muted/50 flex h-8 w-full min-w-14 rounded-md border px-2 py-1 text-sm file:border-0 file:bg-transparent file:text-sm file:font-medium focus:ring-0 focus-visible:ring-offset-0 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

export { Input };
