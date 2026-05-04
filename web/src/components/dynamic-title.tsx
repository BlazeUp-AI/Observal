"use client";

import { useEffect } from "react";
import { useDeploymentConfig } from "@/hooks/use-deployment-config";

export function DynamicTitle() {
  const { brandingAppName } = useDeploymentConfig();

  useEffect(() => {
    document.title = brandingAppName || "Observal";
  }, [brandingAppName]);

  return null;
}
