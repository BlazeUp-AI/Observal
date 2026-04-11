"use client";

import { use } from "react";
import { Puzzle } from "lucide-react";
import { toast } from "sonner";
import { useRegistryItem } from "@/hooks/use-api";
import { PullCommand } from "@/components/registry/pull-command";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layouts/page-header";
import { DetailSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: agent, isLoading, isError, error, refetch } = useRegistryItem("agents", id);

  const a = agent as any;
  const components = a?.component_links ?? a?.mcp_links ?? [];
  const goalTemplate = a?.goal_template;
  const agentName = a?.name ?? id.slice(0, 8);

  return (
    <>
      <PageHeader
        title={isLoading ? "Agent" : agentName}
        breadcrumbs={[
          { label: "Registry", href: "/" },
          { label: "Agents", href: "/agents" },
          { label: isLoading ? "..." : agentName },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {isLoading ? (
          <DetailSkeleton />
        ) : isError ? (
          <ErrorState message={error?.message} onRetry={() => refetch()} />
        ) : !agent ? (
          <ErrorState message="Agent not found" />
        ) : (
          <>
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                {a.version && <Badge variant="secondary">{a.version}</Badge>}
                {a.status && <Badge variant={a.status === "approved" ? "default" : "outline"}>{a.status}</Badge>}
              </div>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                {a.model_name && <span>{a.model_name}</span>}
                {a.owner && <span>{a.owner}</span>}
              </div>
            </div>

            <PullCommand agentName={a.name} />

            <Tabs defaultValue="overview">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="components">Components</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="space-y-4 mt-4">
                {a.description && <p className="text-sm">{a.description}</p>}
                {goalTemplate && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-medium">Goal Template</h3>
                    {goalTemplate.description && <p className="text-sm text-muted-foreground">{goalTemplate.description}</p>}
                    {goalTemplate.sections?.map((sec: any, i: number) => (
                      <div key={i} className="border border-border rounded-sm p-3">
                        <p className="text-sm font-medium">{sec.name}</p>
                        {sec.description && <p className="text-xs text-muted-foreground mt-1">{sec.description}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="components" className="mt-4">
                {components.length === 0 ? (
                  <EmptyState
                    icon={Puzzle}
                    title="No components linked"
                    description="This agent does not have any linked MCP servers or components."
                  />
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Type</TableHead>
                          <TableHead>Name</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {components.map((comp: any, i: number) => (
                          <TableRow key={i}>
                            <TableCell>
                              <Badge variant="outline">{comp.component_type ?? "mcp"}</Badge>
                            </TableCell>
                            <TableCell>{comp.mcp_name ?? comp.component_name ?? comp.name ?? "-"}</TableCell>
                            <TableCell className="text-muted-foreground">{comp.status ?? "-"}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </>
  );
}
