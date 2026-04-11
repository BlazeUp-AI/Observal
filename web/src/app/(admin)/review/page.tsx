"use client";

import { ClipboardCheck } from "lucide-react";
import { useReviewList, useReviewAction } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layouts/page-header";
import { TableSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

export default function ReviewPage() {
  const { data: items, isLoading, isError, error, refetch } = useReviewList();
  const approve = useReviewAction();

  async function handleApprove(id: string) {
    await approve.mutateAsync({ id, action: "approve" });
  }

  async function handleReject(id: string) {
    await approve.mutateAsync({ id, action: "reject" });
  }

  return (
    <>
      <PageHeader
        title="Review Queue"
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Review" },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-4">
        {isLoading ? (
          <TableSkeleton rows={5} cols={4} />
        ) : isError ? (
          <ErrorState message={error?.message} onRetry={() => refetch()} />
        ) : (items ?? []).length === 0 ? (
          <EmptyState
            icon={ClipboardCheck}
            title="No pending reviews"
            description="All submissions have been reviewed. New items will appear here when agents or components are submitted."
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(items ?? []).map((item: any) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell><Badge variant="outline">{item.type ?? "-"}</Badge></TableCell>
                    <TableCell><Badge variant="secondary">{item.status}</Badge></TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="default" onClick={() => handleApprove(item.id)}>
                          Approve
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleReject(item.id)}>
                          Reject
                        </Button>
                      </div>
                    </TableCell>
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
