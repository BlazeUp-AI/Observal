import { PageHeader } from "@/components/layout/PageHeader";
import { useApiQuery } from "@/lib/api";
import { DataTable, Badge, Spinner } from "@/components/ui";

const roleVariant = { admin: "default", developer: "outline", user: "outline" } as const;

export default function Settings() {
  const { data: settings, loading: l1 } = useApiQuery<any[]>("/api/v1/admin/settings");
  const { data: users, loading: l2 } = useApiQuery<any[]>("/api/v1/admin/users");

  if (l1 || l2) return <div className="flex h-64 items-center justify-center"><Spinner /></div>;

  return (
    <div>
      <PageHeader title="Settings" description="Enterprise configuration and user management" />
      {(settings ?? []).length > 0 && (
        <div className="mb-6">
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">Enterprise Settings</h3>
          <DataTable columns={[
            { key: "key", label: "Key", className: "font-mono font-medium" },
            { key: "value", label: "Value" },
          ]} data={settings!} />
        </div>
      )}
      {(users ?? []).length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">Users ({users!.length})</h3>
          <DataTable columns={[
            { key: "name", label: "Name", className: "font-medium" },
            { key: "email", label: "Email" },
            { key: "role", label: "Role", render: (r: any) => <Badge variant={roleVariant[r.role as keyof typeof roleVariant] ?? "outline"}>{r.role}</Badge> },
          ]} data={users!} />
        </div>
      )}
    </div>
  );
}
