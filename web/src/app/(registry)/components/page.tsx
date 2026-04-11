"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Puzzle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useRegistryList } from "@/hooks/use-api";
import type { RegistryType } from "@/lib/api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layouts/page-header";
import { TableSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

const TYPES: { value: RegistryType; label: string }[] = [
  { value: "mcps", label: "MCPs" },
  { value: "skills", label: "Skills" },
  { value: "hooks", label: "Hooks" },
  { value: "prompts", label: "Prompts" },
  { value: "sandboxes", label: "Sandboxes" },
];

function ComponentTable({ type, search }: { type: RegistryType; search: string }) {
  const { data, isLoading, isError, error, refetch } = useRegistryList(type, search ? { search } : undefined);
  const items = data ?? [];

  if (isLoading) return <TableSkeleton rows={5} cols={3} />;
  if (isError) return <ErrorState message={error?.message} onRetry={() => refetch()} />;
  if (items.length === 0) {
    return (
      <EmptyState
        icon={Puzzle}
        title={`No ${type} found`}
        description={search ? `No ${type} match "${search}". Try a different search.` : `No ${type} have been registered yet.`}
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item: any) => (
            <TableRow key={item.id}>
              <TableCell>
                <Link href={`/components/${item.id}?type=${type}`} className="font-medium hover:underline">
                  {item.name}
                </Link>
              </TableCell>
              <TableCell className="text-muted-foreground text-xs max-w-xs truncate">
                {item.description ?? "-"}
              </TableCell>
              <TableCell>
                <Badge variant={item.status === "approved" ? "default" : "secondary"}>
                  {item.status}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default function ComponentsPage() {
  const [search, setSearch] = useState("");

  return (
    <>
      <PageHeader
        title="Components"
        breadcrumbs={[
          { label: "Registry", href: "/" },
          { label: "Components" },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-4">
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search components..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <Tabs defaultValue="mcps">
          <TabsList>
            {TYPES.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
            ))}
          </TabsList>
          {TYPES.map((t) => (
            <TabsContent key={t.value} value={t.value} className="mt-4">
              <ComponentTable type={t.value} search={search} />
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </>
  );
}
