import { PageHeader } from "@/components/layout/PageHeader";
import { useApiQuery } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import { DataTable, Badge, Spinner, EmptyState } from "@/components/ui";
import { Users as UsersIcon } from "lucide-react";

const roleVariant = { admin: "default", developer: "outline", user: "outline" } as const;

export default function Users() {
  const { data, loading } = useApiQuery<any[]>("/api/v1/admin/users");

  if (loading) return <div className="flex h-64 items-center justify-center"><Spinner /></div>;

  const users = data ?? [];
  if (!users.length) return <EmptyState icon={<UsersIcon className="h-8 w-8" />} title="No users" />;

  return (
    <div>
      <PageHeader title="Users" description={`${users.length} user${users.length !== 1 ? "s" : ""}`} />
      <DataTable
        columns={[
          { key: "name", label: "Name", className: "font-medium" },
          { key: "email", label: "Email" },
          { key: "role", label: "Role", render: (r: any) => <Badge variant={roleVariant[r.role as keyof typeof roleVariant] ?? "outline"}>{r.role}</Badge> },
          { key: "created_at", label: "Created", render: (r: any) => r.created_at ? formatRelativeTime(r.created_at) : "—" },
        ]}
        data={users}
      />
    </div>
  );
}
