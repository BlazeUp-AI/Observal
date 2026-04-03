import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border border-transparent font-semibold transition-colors focus:outline-hidden focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground",
        secondary: "bg-secondary text-secondary-foreground",
        destructive: "bg-destructive text-destructive-foreground",
        outline: "border-input bg-background text-foreground",
        success: "bg-light-green text-dark-green",
        error: "bg-light-red text-dark-red",
        warning: "bg-light-yellow text-dark-yellow",
      },
      size: {
        default: "px-2.5 py-0.5 text-xs",
        sm: "px-1 py-0 text-xs",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>;

function Badge({ className, variant, size, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, size }), className)} {...props} />;
}

export { Badge, badgeVariants };
