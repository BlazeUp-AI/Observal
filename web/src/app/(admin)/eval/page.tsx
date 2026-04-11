"use client";

import Link from "next/link";
import { useRegistryList } from "@/hooks/use-api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function EvalPage() {
  const { data: agents, isLoading } = useRegistryList("agents");

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Eval</h1>
      <p className="text-sm text-muted-foreground">Select an agent to view evaluation scores and run evals.</p>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Agent</TableHead>
            <TableHead>Version</TableHead>
            <TableHead>Model</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow><TableCell colSpan={3} className="text-center text-muted-foreground">Loading...</TableCell></TableRow>
          ) : (agents ?? []).length === 0 ? (
            <TableRow><TableCell colSpan={3} className="text-center text-muted-foreground">No agents</TableCell></TableRow>
          ) : (
            (agents ?? []).map((a: any) => (
              <TableRow key={a.id}>
                <TableCell>
                  <Link href={`/eval/${a.id}`} className="font-medium hover:underline">{a.name}</Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{a.version ?? "-"}</TableCell>
                <TableCell className="text-muted-foreground">{a.model_name ?? "-"}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
