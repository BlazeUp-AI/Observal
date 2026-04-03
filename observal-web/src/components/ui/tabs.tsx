import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export type Tab = { value: string; label: string; count?: number };

export function TabsList({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("flex border-b border-border", className)}>{children}</div>;
}

export function TabsTrigger({
  active,
  onClick,
  className,
  children,
}: {
  active?: boolean;
  onClick?: () => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
        active
          ? "border-primary text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground",
        className
      )}
    >
      {children}
    </button>
  );
}

export function Tabs({
  tabs,
  value,
  onValueChange,
  className,
}: {
  tabs: Tab[];
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}) {
  return (
    <TabsList className={className}>
      {tabs.map((tab) => (
        <TabsTrigger key={tab.value} active={tab.value === value} onClick={() => onValueChange(tab.value)}>
          {tab.label}
          {tab.count !== undefined && (
            <span className="ml-1.5 text-xs text-muted-foreground">({tab.count})</span>
          )}
        </TabsTrigger>
      ))}
    </TabsList>
  );
}
