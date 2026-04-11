"use client";

import { use } from "react";
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

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: agent, isLoading } = useRegistryItem("agents", id);

  if (isLoading) return <div className="p-6 text-muted-foreground">Loading...</div>;
  if (!agent) return <div className="p-6 text-muted-foreground">Agent not found</div>;

  const a = agent as any;
  const components = a.component_links ?? a.mcp_links ?? [];
  const goalTemplate = a.goal_template;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold">{a.name}</h1>
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
            <p className="text-sm text-muted-foreground">No components linked</p>
          ) : (
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
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
