"use client";
import { useAuthGuard, useOptionalAuth } from "@/hooks/use-auth";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  useAuthGuard();
  // Render children immediately to prevent hydration mismatch
  // The useAuthGuard hook handles redirects via side effects
  return <>{children}</>;
}

/**
 * Allows unauthenticated browsing — renders children regardless of auth state.
 * Resolves role for authenticated users so sidebar can show/hide admin items.
 */
export function OptionalAuthGuard({ children }: { children: React.ReactNode }) {
  useOptionalAuth();
  // Render children immediately to prevent hydration mismatch
  return <>{children}</>;
}
