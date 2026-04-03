import { PageHeader } from "@/components/layout/PageHeader";
import { useNavigate } from "react-router-dom";
import { useApiQuery } from "@/lib/api";
import { DataTable, Badge, Spinner, EmptyState } from "@/components/ui";
import { StatusBadge } from "@/components/ui/status-badge";
import { Bot } from "lucide-react";

export default function Agents() {
  const { data, loading } = useApiQuery<any[]>("/api/v1/agents");
  const navigate = useNavigate();

  if (loading) return <div className="flex h-64 items-center justify-center"><Spinner /></div>;

  const agents = data ?? [];
  if (!agents.length) return <EmptyState icon={<Bot className="h-8 w-8" />} title="No agents" description="Create one via the CLI: observal agent create" />;

  return (
    <div>
      <PageHeader title="Agents" description={`${agents.length} active`} />
      <DataTable
        columns={[
          { key: "name", label: "Name", className: "font-medium" },
          { key: "version", label: "Version", className: "font-mono text-xs" },
          { key: "model_name", label: "Model" },
          { key: "owner", label: "Owner", className: "text-muted-foreground" },
          { key: "supported_ides", label: "IDEs", render: (r: any) => (r.supported_ides || []).map((ide: string) => <Badge key={ide} variant="outline">{ide}</Badge>) },
          { key: "status", label: "Status", render: (r: any) => <StatusBadge status={r.status ?? "active"} /> },
        ]}
        data={agents}
        onRowClick={(r) => navigate(`/agents/${r.id}`)}
      />
    </div>
  );
}
