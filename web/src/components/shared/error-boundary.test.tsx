// SPDX-FileCopyrightText: 2026 Satej More <satejmore28@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * web/src/components/shared/error-boundary.test.tsx
 *
 * Tests for CardErrorBoundary.
 *
 * Run with:
 *   pnpm test  (or: npx vitest run src/components/shared/error-boundary.test.tsx)
 *
 * Dependencies already present in the repo:
 *   vitest, @testing-library/react, @testing-library/user-event
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { CardErrorBoundary } from "./error-boundary";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let bombCount = 0;

/** A component that throws on first render, then succeeds on re-renders. */
function BombOnce({ message = "boom" }: { message?: string }): React.ReactNode {
    // eslint-disable-next-line react-hooks/globals
    bombCount += 1;
    if (bombCount === 1) {
        throw new Error(message);
    }
    return <div data-testid="recovered">Recovered</div>;
}

/** A component that always throws. */
function AlwaysBomb({ message = "always fails" }: { message?: string }): React.ReactNode {
    throw new Error(message);
}

/** Suppresses expected console.error noise from React error boundaries. */
function suppressConsoleError() {
    const spy = vi.spyOn(console, "error").mockImplementation(() => { });
    return () => spy.mockRestore();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CardErrorBoundary", () => {
    let restore: () => void;

    beforeEach(() => {
        bombCount = 0;
        restore = suppressConsoleError();
    });

    afterEach(() => {
        restore();
    });

    // ── Fallback rendering ────────────────────────────────────────────────

    it("renders children when there is no error", () => {
        render(
            <CardErrorBoundary label="Test Card">
                <div data-testid="child">Hello</div>
            </CardErrorBoundary>,
        );
        expect(screen.getByTestId("child")).toBeInTheDocument();
    });

    it("renders the default fallback when a child throws", () => {
        render(
            <CardErrorBoundary label="Failing Card">
                <AlwaysBomb message="test error" />
            </CardErrorBoundary>,
        );

        expect(screen.getByRole("alert")).toBeInTheDocument();
        expect(screen.getByText(/Failing Card failed to load/i)).toBeInTheDocument();
        expect(screen.getByText(/test error/i)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("shows generic message when no label is provided", () => {
        render(
            <CardErrorBoundary>
                <AlwaysBomb />
            </CardErrorBoundary>,
        );
        expect(screen.getByText(/this card failed to load/i)).toBeInTheDocument();
    });

    // ── Retry behaviour ───────────────────────────────────────────────────

    it("remounts children when Retry is clicked", () => {
        render(
            <CardErrorBoundary label="Bomb Once">
                <BombOnce message="first render boom" />
            </CardErrorBoundary>,
        );

        // First render: boundary catches, shows fallback.
        expect(screen.getByRole("alert")).toBeInTheDocument();

        // Click retry: boundary resets, BombOnce succeeds on second render.
        fireEvent.click(screen.getByRole("button", { name: /retry/i }));

        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.getByTestId("recovered")).toBeInTheDocument();
    });

    // ── Sibling isolation ─────────────────────────────────────────────────

    it("does not affect sibling boundaries when one card crashes", () => {
        render(
            <div>
                <CardErrorBoundary label="Card A">
                    <AlwaysBomb />
                </CardErrorBoundary>

                <CardErrorBoundary label="Card B">
                    <div data-testid="card-b-content">Card B is fine</div>
                </CardErrorBoundary>
            </div>,
        );

        // Card A is in error state.
        expect(screen.getByText(/Card A failed to load/i)).toBeInTheDocument();

        // Card B still renders normally.
        expect(screen.getByTestId("card-b-content")).toBeInTheDocument();
        expect(screen.queryByText(/Card B failed to load/i)).not.toBeInTheDocument();
    });

    it("isolates multiple simultaneous failures independently", () => {
        render(
            <div>
                <CardErrorBoundary label="Card A">
                    <AlwaysBomb message="error A" />
                </CardErrorBoundary>

                <CardErrorBoundary label="Card B">
                    <AlwaysBomb message="error B" />
                </CardErrorBoundary>

                <CardErrorBoundary label="Card C">
                    <div data-testid="card-c">OK</div>
                </CardErrorBoundary>
            </div>,
        );

        expect(screen.getByText(/Card A failed to load/i)).toBeInTheDocument();
        expect(screen.getByText(/error A/i)).toBeInTheDocument();

        expect(screen.getByText(/Card B failed to load/i)).toBeInTheDocument();
        expect(screen.getByText(/error B/i)).toBeInTheDocument();

        expect(screen.getByTestId("card-c")).toBeInTheDocument();
    });

    // ── Custom fallback prop ──────────────────────────────────────────────

    it("renders a custom fallback when the fallback prop is supplied", () => {
        const customFallback = (reset: () => void, error: Error) => (
            <button data-testid="custom" onClick={reset}>
                Custom: {error.message}
            </button>
        );

        render(
            <CardErrorBoundary label="Custom" fallback={customFallback}>
                <AlwaysBomb message="custom error" />
            </CardErrorBoundary>,
        );

        expect(screen.getByTestId("custom")).toBeInTheDocument();
        expect(screen.getByText(/custom error/i)).toBeInTheDocument();
        // Default fallback must NOT appear alongside the custom one.
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("passes a working reset callback to the custom fallback", () => {
        render(
            <CardErrorBoundary
                fallback={(reset) => (
                    <button data-testid="custom-retry" onClick={reset}>
                        Reset
                    </button>
                )}
            >
                <BombOnce />
            </CardErrorBoundary>,
        );

        expect(screen.getByTestId("custom-retry")).toBeInTheDocument();

        fireEvent.click(screen.getByTestId("custom-retry"));

        expect(screen.queryByTestId("custom-retry")).not.toBeInTheDocument();
        expect(screen.getByTestId("recovered")).toBeInTheDocument();
    });

    // ── No regression: successful query cards still render ────────────────

    it("does not interfere with normal children that never throw", () => {
        const { rerender } = render(
            <CardErrorBoundary label="Stable Card">
                <div data-testid="stable">Stable content</div>
            </CardErrorBoundary>,
        );

        expect(screen.getByTestId("stable")).toBeInTheDocument();

        // Re-render with updated content — still no error boundary interference.
        rerender(
            <CardErrorBoundary label="Stable Card">
                <div data-testid="stable">Updated content</div>
            </CardErrorBoundary>,
        );

        expect(screen.getByTestId("stable")).toHaveTextContent("Updated content");
    });
});