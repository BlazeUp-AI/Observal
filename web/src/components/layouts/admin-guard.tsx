"use client";

import { RoleGuard } from "@/components/layouts/role-guard";

/**
 * @deprecated Use `<RoleGuard minRole="admin">` instead.
 * Kept for backward compatibility.
 */
export function AdminGuard({ children }: { children: React.ReactNode }) {
  return <RoleGuard minRole="admin">{children}</RoleGuard>;
}
