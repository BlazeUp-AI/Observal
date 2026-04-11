"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useRegistryList } from "@/hooks/use-api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export default function AgentListPage() {
  const searchParams = useSearchParams();
  const initialSearch = searchParams.get("search") ?? "";
  const [search, setSearch] = useState(initialSearch);
  const { data: agents, isLoading } = useRegistryList("agents", search ? { search } : undefined);

  const filtered = agents ?? [];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Agents</h1>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Filter agents..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Model</TableHead>
            <TableHead>Owner</TableHead>
            <TableHead>Version</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Loading...</TableCell></TableRow>
          ) : filtered.length === 0 ? (
            <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">No agents found</TableCell></TableRow>
          ) : (
            filtered.map((agent: any) => (
              <TableRow key={agent.id}>
                <TableCell>
                  <Link href={`/agents/${agent.id}`} className="font-medium hover:underline">{agent.name}</Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{agent.model_name ?? "-"}</TableCell>
                <TableCell className="text-muted-foreground">{agent.owner ?? "-"}</TableCell>
                <TableCell className="text-muted-foreground">{agent.version ?? "-"}</TableCell>
                <TableCell>
                  <Badge variant={agent.status === "approved" ? "default" : "secondary"}>
                    {agent.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
