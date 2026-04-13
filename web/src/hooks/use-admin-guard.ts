"use client";

import { useRoleGuard } from "@/hooks/use-role-guard";

/**
 * @deprecated Use `useRoleGuard("admin")` instead.
 * Kept for backward compatibility.
 */
export function useAdminGuard() {
  const { ready } = useRoleGuard("admin");
  return ready;
}
