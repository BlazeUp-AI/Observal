import { PageHeader } from "@/components/layout/PageHeader";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApiQuery } from "@/lib/api";
import { DataTable, Badge, Spinner, EmptyState } from "@/components/ui";
import { StatusBadge } from "@/components/ui/status-badge";
import { Input } from "@/components/ui/input";
import { Server } from "lucide-react";

export default function McpServers() {
  const { data, loading } = useApiQuery<any[]>("/api/v1/mcps");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const navigate = useNavigate();

  if (loading) return <div className="flex h-64 items-center justify-center"><Spinner /></div>;

  const mcps = data ?? [];
  if (!mcps.length) return <EmptyState icon={<Server className="h-8 w-8" />} title="No MCP servers" description="Submit one via the CLI: observal submit <git-url>" />;

  const categories = [...new Set(mcps.map((m) => m.category).filter(Boolean))];
  const filtered = mcps.filter((m) => {
    const s = !search || m.name?.toLowerCase().includes(search.toLowerCase());
    const c = !category || m.category === category;
    return s && c;
  });

  return (
    <div>
      <PageHeader title="MCP Servers" description={`${filtered.length} server${filtered.length !== 1 ? "s" : ""}`} />
      <div className="mb-4 flex gap-3">
        <Input placeholder="Search servers…" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <DataTable
        columns={[
          { key: "name", label: "Name", className: "font-medium" },
          { key: "version", label: "Version", className: "font-mono text-xs" },
          { key: "category", label: "Category", render: (r: any) => <Badge variant="outline">{r.category}</Badge> },
          { key: "owner", label: "Owner", className: "text-muted-foreground" },
          { key: "supported_ides", label: "IDEs", render: (r: any) => (r.supported_ides || []).map((ide: string) => <Badge key={ide} variant="outline">{ide}</Badge>) },
          { key: "status", label: "Status", render: (r: any) => <StatusBadge status={r.status ?? "approved"} /> },
        ]}
        data={filtered}
        onRowClick={(r) => navigate(`/mcps/${r.id}`)}
      />
    </div>
  );
}
