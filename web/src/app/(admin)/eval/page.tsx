"use client";

import Link from "next/link";
import { FlaskConical } from "lucide-react";
import { useRegistryList } from "@/hooks/use-api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layouts/page-header";
import { TableSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

export default function EvalPage() {
  const { data: agents, isLoading, isError, error, refetch } = useRegistryList("agents");

  return (
    <>
      <PageHeader
        title="Eval"
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Eval" },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-4">
        <p className="text-sm text-muted-foreground">Select an agent to view evaluation scores and run evals.</p>

        {isLoading ? (
          <TableSkeleton rows={5} cols={3} />
        ) : isError ? (
          <ErrorState message={error?.message} onRetry={() => refetch()} />
        ) : (agents ?? []).length === 0 ? (
          <EmptyState
            icon={FlaskConical}
            title="No agents to evaluate"
            description="Submit an agent to the registry to run evaluations against it."
            actionLabel="Browse Agents"
            actionHref="/agents"
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Model</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(agents ?? []).map((a: any) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      <Link href={`/eval/${a.id}`} className="font-medium hover:underline">{a.name}</Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{a.version ?? "-"}</TableCell>
                    <TableCell className="text-muted-foreground">{a.model_name ?? "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </>
  );
}
