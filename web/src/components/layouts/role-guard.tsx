"use client";

import { useRoleGuard, type Role } from "@/hooks/use-role-guard";

export function RoleGuard({ minRole, children }: { minRole: Role; children: React.ReactNode }) {
  useRoleGuard(minRole);
  // Render children immediately to prevent hydration mismatch
  // The useRoleGuard hook handles redirects via side effects
  return <>{children}</>;
}
