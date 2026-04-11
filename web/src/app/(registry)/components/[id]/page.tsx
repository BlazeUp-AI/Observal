"use client";

import { use } from "react";
import { useSearchParams } from "next/navigation";
import { useRegistryItem } from "@/hooks/use-api";
import type { RegistryType } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/layouts/page-header";
import { DetailSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";

export default function ComponentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const type = (searchParams.get("type") ?? "mcps") as RegistryType;
  const { data: item, isLoading, isError, error, refetch } = useRegistryItem(type, id);

  const componentName = item?.name ?? id.slice(0, 8);

  return (
    <>
      <PageHeader
        title={isLoading ? "Component" : componentName}
        breadcrumbs={[
          { label: "Registry", href: "/" },
          { label: "Components", href: "/components" },
          { label: isLoading ? "..." : componentName },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {isLoading ? (
          <DetailSkeleton />
        ) : isError ? (
          <ErrorState message={error?.message} onRetry={() => refetch()} />
        ) : !item ? (
          <ErrorState message="Component not found" />
        ) : (
          <>
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="outline">{type.replace(/s$/, "")}</Badge>
                {item.status && <Badge variant={item.status === "approved" ? "default" : "secondary"}>{item.status}</Badge>}
              </div>
            </div>

            {item.description && <p className="text-sm">{item.description}</p>}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              {"version" in item && item.version != null && <div><span className="text-muted-foreground">Version:</span> {String(item.version)}</div>}
              {"git_url" in item && item.git_url != null && <div><span className="text-muted-foreground">Source:</span> <a href={String(item.git_url)} className="underline" target="_blank" rel="noopener noreferrer">{String(item.git_url)}</a></div>}
              {"transport" in item && item.transport != null && <div><span className="text-muted-foreground">Transport:</span> {String(item.transport)}</div>}
              {item.created_at && <div><span className="text-muted-foreground">Created:</span> {new Date(item.created_at).toLocaleDateString()}</div>}
            </div>
          </>
        )}
      </div>
    </>
  );
}
