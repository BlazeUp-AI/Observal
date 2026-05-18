// SPDX-FileCopyrightText: 2026 Satej More <satejmore28@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

"use client";

/**
 * web/src/components/shared/error-boundary.tsx
 *
 * Class-based React error boundary that isolates dashboard cards so one
 * crashing render does not blank sibling cards.
 *
 * Usage:
 *   import { CardErrorBoundary } from "@/components/shared/error-boundary";
 *
 *   <CardErrorBoundary label="MCP Metrics">
 *     <McpMetricsCard />
 *   </CardErrorBoundary>
 */

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CardErrorBoundaryProps {
    /** Human-readable label shown in the fallback (e.g. "MCP Metrics"). */
    label?: string;
    /** Override the full fallback UI. Receives a reset callback. */
    fallback?: (reset: () => void, error: Error) => ReactNode;
    /** Extra classes applied to the outer wrapper div. */
    className?: string;
    children: ReactNode;
}

interface CardErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
    /**
     * Incrementing this key forces React to unmount + remount children,
     * which is the correct way to "retry" after an error boundary catches.
     */
    resetKey: number;
}

// ---------------------------------------------------------------------------
// Default fallback — mirrors the visual style of query-error.tsx
// ---------------------------------------------------------------------------

function DefaultFallback({
    label,
    error,
    onRetry,
}: {
    label?: string;
    error: Error;
    onRetry: () => void;
}) {
    return (
        <div
            role="alert"
            aria-live="assertive"
            className={cn(
                "flex h-full min-h-[120px] w-full flex-col items-center justify-center gap-3",
                "rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-center",
            )}
        >
            <AlertTriangle
                className="h-6 w-6 text-destructive/70"
                aria-hidden="true"
            />

            <div className="space-y-0.5">
                <p className="text-sm font-medium text-destructive">
                    {label ? `${label} failed to load` : "This card failed to load"}
                </p>
                <p className="max-w-[28ch] text-xs text-muted-foreground">
                    {error?.message ?? "An unexpected error occurred."}
                </p>
            </div>

            <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
                className="mt-1 h-7 gap-1.5 border-destructive/30 text-xs text-destructive hover:bg-destructive/10"
            >
                <RefreshCw className="h-3 w-3" aria-hidden="true" />
                Retry
            </Button>
        </div>
    );
}

// ---------------------------------------------------------------------------
// CardErrorBoundary
// ---------------------------------------------------------------------------

export class CardErrorBoundary extends Component<
    CardErrorBoundaryProps,
    CardErrorBoundaryState
> {
    static displayName = "CardErrorBoundary";

    constructor(props: CardErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null, resetKey: 0 };
        this.reset = this.reset.bind(this);
    }

    // Invoked during render; updates state so the next render shows fallback.
    static getDerivedStateFromError(error: Error): Partial<CardErrorBoundaryState> {
        return { hasError: true, error };
    }

    // Invoked after the tree has thrown; good place for logging.
    componentDidCatch(error: Error, info: ErrorInfo) {
        // Surface to any error-tracking service (Sentry, DataDog, etc.) here.
        if (process.env.NODE_ENV !== "production") {
            console.error(
                `[CardErrorBoundary]${this.props.label ? ` (${this.props.label})` : ""}`,
                error,
                info.componentStack,
            );
        }
    }

    /**
     * Resetting increments `resetKey`, which is spread onto the children
     * wrapper below as `key`.  This forces React to fully unmount and remount
     * the subtree — the correct way to "retry" inside an error boundary.
     */
    reset() {
        this.setState((prev) => ({
            hasError: false,
            error: null,
            resetKey: prev.resetKey + 1,
        }));
    }

    render() {
        const { hasError, error, resetKey } = this.state;
        const { children, label, fallback, className } = this.props;

        if (hasError && error) {
            return (
                <div className={cn("contents", className)}>
                    {fallback ? (
                        fallback(this.reset, error)
                    ) : (
                        <DefaultFallback label={label} error={error} onRetry={this.reset} />
                    )}
                </div>
            );
        }

        return (
            // key change triggers remount of the entire child subtree on retry.
            <div key={resetKey} className={cn("contents", className)}>
                {children}
            </div>
        );
    }
}

// ---------------------------------------------------------------------------
// Convenience re-export so callers can also use it as a default import.
// ---------------------------------------------------------------------------
export default CardErrorBoundary;