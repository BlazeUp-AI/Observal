"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getUserRole } from "@/lib/api";

export function useAdminGuard() {
  const router = useRouter();
  const [ready] = useState(() => {
    if (typeof window === "undefined") return false;
    return getUserRole() === "admin";
  });

  useEffect(() => {
    if (!ready) {
      router.replace("/");
    }
  }, [ready, router]);

  return ready;
}
