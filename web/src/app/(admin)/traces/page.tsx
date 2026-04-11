"use client";

import Link from "next/link";
import { useOtelSessions } from "@/hooks/use-api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function TracesPage() {
  const { data: sessions, isLoading } = useOtelSessions();

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Traces</h1>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Session ID</TableHead>
            <TableHead>Service</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow><TableCell colSpan={2} className="text-center text-muted-foreground">Loading...</TableCell></TableRow>
          ) : (sessions ?? []).length === 0 ? (
            <TableRow><TableCell colSpan={2} className="text-center text-muted-foreground">No traces</TableCell></TableRow>
          ) : (
            (sessions ?? []).map((s: any) => (
              <TableRow key={s.session_id}>
                <TableCell>
                  <Link href={`/traces/${s.session_id}`} className="font-mono text-xs hover:underline">
                    {s.session_id}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{s.service_name ?? "-"}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
