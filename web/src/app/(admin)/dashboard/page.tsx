"use client";

import Link from "next/link";
import { useOverviewStats, useRegistryList, useTopAgents, useOtelSessions } from "@/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border border-border rounded-sm p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}

export default function DashboardPage() {
  const { data: stats } = useOverviewStats();
  const { data: agents } = useRegistryList("agents");
  const { data: topAgents } = useTopAgents();
  const { data: sessions } = useOtelSessions();

  const recentSessions = (sessions ?? []).slice(0, 10);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Agents Deployed" value={stats?.total_agents ?? 0} />
        <StatCard label="Total Downloads" value={topAgents?.reduce((s: number, a: any) => s + a.value, 0) ?? 0} />
        <StatCard label="Users" value={stats?.total_users ?? 0} />
        <StatCard label="Components" value={stats?.total_mcps ?? 0} />
      </div>

      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-3">Agents</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(agents ?? []).slice(0, 20).map((a: any) => (
              <TableRow key={a.id}>
                <TableCell>
                  <Link href={`/agents/${a.id}`} className="font-medium hover:underline">{a.name}</Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{a.version ?? "-"}</TableCell>
                <TableCell className="text-muted-foreground">{a.model_name ?? "-"}</TableCell>
                <TableCell>
                  <Badge variant={a.status === "approved" ? "default" : "secondary"}>{a.status}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      {recentSessions.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">Recent Traces</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Session</TableHead>
                <TableHead>Service</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentSessions.map((s: any) => (
                <TableRow key={s.session_id}>
                  <TableCell>
                    <Link href={`/traces/${s.session_id}`} className="font-mono text-xs hover:underline">
                      {s.session_id.slice(0, 12)}...
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{s.service_name ?? "-"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>
      )}
    </div>
  );
}
