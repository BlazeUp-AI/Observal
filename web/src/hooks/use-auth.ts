"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

export function useAuthGuard() {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const key = localStorage.getItem("observal_api_key");
    if (!key && pathname !== "/login") {
      router.replace("/login");
    } else {
      setChecked(true);
    }
  }, [pathname, router]);

  return checked;
}
