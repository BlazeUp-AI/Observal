"use client";

import Link from "next/link";
import { LayoutDashboard, Bot, Activity } from "lucide-react";
import { useOverviewStats, useRegistryList, useTopAgents, useOtelSessions } from "@/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layouts/page-header";
import { CardSkeleton, TableSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border border-border rounded-sm p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading, isError: statsError, error: statsErr, refetch: refetchStats } = useOverviewStats();
  const { data: agents, isLoading: agentsLoading, isError: agentsError, error: agentsErr, refetch: refetchAgents } = useRegistryList("agents");
  const { data: topAgents } = useTopAgents();
  const { data: sessions, isLoading: sessionsLoading } = useOtelSessions();

  const recentSessions = (sessions ?? []).slice(0, 10);

  return (
    <>
      <PageHeader
        title="Dashboard"
        breadcrumbs={[
          { label: "Dashboard" },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-8">
        {statsLoading ? (
          <CardSkeleton count={4} />
        ) : statsError ? (
          <ErrorState message={statsErr?.message} onRetry={() => refetchStats()} />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Agents Deployed" value={stats?.total_agents ?? 0} />
            <StatCard label="Total Downloads" value={topAgents?.reduce((s: number, a: any) => s + a.value, 0) ?? 0} />
            <StatCard label="Users" value={stats?.total_users ?? 0} />
            <StatCard label="Components" value={stats?.total_mcps ?? 0} />
          </div>
        )}

        <section>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">Agents</h2>
          {agentsLoading ? (
            <TableSkeleton rows={5} cols={4} />
          ) : agentsError ? (
            <ErrorState message={agentsErr?.message} onRetry={() => refetchAgents()} />
          ) : (agents ?? []).length === 0 ? (
            <EmptyState
              icon={Bot}
              title="No agents deployed"
              description="Agents will appear here once they are submitted to the registry."
              actionLabel="Browse Registry"
              actionHref="/agents"
            />
          ) : (
            <div className="overflow-x-auto">
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
            </div>
          )}
        </section>

        <section>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">Recent Traces</h2>
          {sessionsLoading ? (
            <TableSkeleton rows={5} cols={2} />
          ) : recentSessions.length === 0 ? (
            <EmptyState
              icon={Activity}
              title="No traces yet"
              description="Traces will appear here once telemetry data is collected."
            />
          ) : (
            <div className="overflow-x-auto">
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
            </div>
          )}
        </section>
      </div>
    </>
  );
}
