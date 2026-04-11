"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Search, Bot } from "lucide-react";
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
import { PageHeader } from "@/components/layouts/page-header";
import { TableSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

export default function AgentListPage() {
  const searchParams = useSearchParams();
  const initialSearch = searchParams.get("search") ?? "";
  const [search, setSearch] = useState(initialSearch);
  const { data: agents, isLoading, isError, error, refetch } = useRegistryList("agents", search ? { search } : undefined);

  const filtered = agents ?? [];

  return (
    <>
      <PageHeader
        title="Agents"
        breadcrumbs={[
          { label: "Registry", href: "/" },
          { label: "Agents" },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-4">
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Filter agents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        {isLoading ? (
          <TableSkeleton rows={8} cols={5} />
        ) : isError ? (
          <ErrorState message={error?.message} onRetry={() => refetch()} />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Bot}
            title="No agents found"
            description={search ? `No agents match "${search}". Try a different search term.` : "No agents have been submitted yet. Be the first to submit one."}
            actionLabel="Submit Your First Agent"
            actionHref="/agents"
          />
        ) : (
          <div className="overflow-x-auto">
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
                {filtered.map((agent: any) => (
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
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </>
  );
}
