"use client";

import { useRoleGuard, type Role } from "@/hooks/use-role-guard";

export function RoleGuard({ minRole, children }: { minRole: Role; children: React.ReactNode }) {
  const { ready } = useRoleGuard(minRole);
  if (!ready) return null;
  return <>{children}</>;
}
