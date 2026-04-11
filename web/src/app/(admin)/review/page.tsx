"use client";

import { useReviewList, useReviewAction } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function ReviewPage() {
  const { data: items, isLoading, refetch } = useReviewList();
  const approve = useReviewAction();

  async function handleApprove(id: string) {
    await approve.mutateAsync({ id, action: "approve" });
    refetch();
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Review Queue</h1>
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
          {isLoading ? (
            <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Loading...</TableCell></TableRow>
          ) : (items ?? []).length === 0 ? (
            <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">No pending reviews</TableCell></TableRow>
          ) : (
            (items ?? []).map((item: any) => (
              <TableRow key={item.id}>
                <TableCell className="font-medium">{item.name}</TableCell>
                <TableCell><Badge variant="outline">{item.type ?? "-"}</Badge></TableCell>
                <TableCell><Badge variant="secondary">{item.status}</Badge></TableCell>
                <TableCell>
                  <Button size="sm" variant="default" onClick={() => handleApprove(item.id)}>
                    Approve
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
