"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { graphql } from "@/lib/api";
import { PageHeader } from "@/components/layouts/page-header";
import { DashboardShell, DashboardContent } from "@/components/layouts/dashboard-shell";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface Score {
  score_id: string;
  trace_id: string;
  span_id?: string;
  name: string;
  source: string;
  data_type: string;
  value?: number;
  string_value?: string;
  comment?: string;
  timestamp: string;
}

const SOURCES = ["all", "human", "eval"];

export default function ScoresPage() {
  const [source, setSource] = useState("all");
  const [nameFilter, setNameFilter] = useState("");

  const { data: scores, isLoading } = useQuery({
    queryKey: ["scores", source],
    queryFn: () =>
      graphql<{ scores: Score[] }>(
        `query Scores($source: String) { scores(source: $source) { score_id trace_id span_id name source data_type value string_value comment timestamp } }`,
        source !== "all" ? { source } : undefined,
      ).then((d) => d.scores),
  });

  const filtered = scores?.filter((s) => !nameFilter || s.name.toLowerCase().includes(nameFilter.toLowerCase()));

  return (
    <DashboardShell>
      <PageHeader title="Scores" breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Scores" }]} />
      <DashboardContent>
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Input placeholder="Filter by name…" value={nameFilter} onChange={(e) => setNameFilter(e.target.value)} className="h-8 max-w-xs text-sm" />
            <Select value={source} onValueChange={setSource}>
              <SelectTrigger className="h-8 w-[140px] text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>{SOURCES.map((s) => <SelectItem key={s} value={s} className="text-sm">{s === "all" ? "All sources" : s}</SelectItem>)}</SelectContent>
            </Select>
          </div>

          {isLoading ? (
            <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}</div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="h-9 px-3 text-xs">Name</TableHead>
                    <TableHead className="h-9 px-3 text-xs">Source</TableHead>
                    <TableHead className="h-9 px-3 text-xs">Type</TableHead>
                    <TableHead className="h-9 px-3 text-xs">Value</TableHead>
                    <TableHead className="h-9 px-3 text-xs">Trace</TableHead>
                    <TableHead className="h-9 px-3 text-xs">Timestamp</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered?.length ? filtered.map((s) => (
                    <TableRow key={s.score_id}>
                      <TableCell className="px-3 py-2 text-sm font-medium">{s.name}</TableCell>
                      <TableCell className="px-3 py-2"><Badge variant={s.source === "human" ? "secondary" : "outline"} className="text-xs">{s.source}</Badge></TableCell>
                      <TableCell className="px-3 py-2 text-sm">{s.data_type}</TableCell>
                      <TableCell className="px-3 py-2 font-mono text-sm">{s.value != null ? s.value : s.string_value ?? "—"}</TableCell>
                      <TableCell className="px-3 py-2">
                        <Link href={`/traces/${s.trace_id}`} className="font-mono text-xs text-primary hover:underline">{s.trace_id.slice(0, 8)}…</Link>
                      </TableCell>
                      <TableCell className="px-3 py-2 text-xs text-muted-foreground">{new Date(s.timestamp).toLocaleString()}</TableCell>
                    </TableRow>
                  )) : (
                    <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground">No scores found</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </DashboardContent>
    </DashboardShell>
  );
}
