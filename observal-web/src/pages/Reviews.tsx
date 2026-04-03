import { PageHeader } from "@/components/layout/PageHeader";
import { useApiQuery } from "@/lib/api";
import { DataTable, Spinner, EmptyState } from "@/components/ui";
import { StatusBadge } from "@/components/ui/status-badge";
import { ClipboardList } from "lucide-react";

export default function Reviews() {
  const { data, loading } = useApiQuery<any[]>("/api/v1/review");

  if (loading) return <div className="flex h-64 items-center justify-center"><Spinner /></div>;

  const reviews = data ?? [];
  if (!reviews.length) return <EmptyState icon={<ClipboardList className="h-8 w-8" />} title="No pending reviews" description="All submissions have been reviewed." />;

  return (
    <div>
      <PageHeader title="Reviews" description={`${reviews.length} pending`} />
      <DataTable
        columns={[
          { key: "name", label: "Name", className: "font-medium" },
          { key: "submitted_by", label: "Submitted By", className: "text-muted-foreground" },
          { key: "status", label: "Status", render: (r: any) => <StatusBadge status={r.status ?? "pending"} /> },
          { key: "git_url", label: "Git URL", render: (r: any) => r.git_url ? <a href={r.git_url} target="_blank" rel="noreferrer" className="text-primary hover:underline truncate max-w-[200px] inline-block">{r.git_url.replace(/^https?:\/\//, "")}</a> : "—" },
        ]}
        data={reviews}
      />
    </div>
  );
}
