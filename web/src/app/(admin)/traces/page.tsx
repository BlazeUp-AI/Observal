"use client";

import Link from "next/link";
import { Activity } from "lucide-react";
import { useOtelSessions } from "@/hooks/use-api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layouts/page-header";
import { TableSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

export default function TracesPage() {
  const { data: sessions, isLoading, isError, error, refetch } = useOtelSessions();

  return (
    <>
      <PageHeader
        title="Traces"
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Traces" },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-4">
        {isLoading ? (
          <TableSkeleton rows={8} cols={2} />
        ) : isError ? (
          <ErrorState message={error?.message} onRetry={() => refetch()} />
        ) : (sessions ?? []).length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No traces yet"
            description="Traces will appear here once telemetry data is collected from your agents."
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Session ID</TableHead>
                  <TableHead>Service</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(sessions ?? []).map((s: any) => (
                  <TableRow key={s.session_id}>
                    <TableCell>
                      <Link href={`/traces/${s.session_id}`} className="font-mono text-xs hover:underline">
                        {s.session_id}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{s.service_name ?? "-"}</TableCell>
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
