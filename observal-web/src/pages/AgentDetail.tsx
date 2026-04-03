import { PageHeader } from "@/components/layout/PageHeader";
import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useApiQuery } from "@/lib/api";
import { formatNumber, formatDuration } from "@/lib/format";
import { Card, Badge, Spinner } from "@/components/ui";
import { StatCard } from "@/components/ui/stat-card";
import { ArrowLeft, Download, Activity, Clock, CheckCircle } from "lucide-react";

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: agent, loading } = useApiQuery<any>(`/api/v1/agents/${id}`);
  const { data: metrics } = useApiQuery<any>(`/api/v1/dashboard/agent/${id}/metrics`);
  const [expanded, setExpanded] = useState(false);

  if (loading) return <div className="flex h-64 items-center justify-center"><Spinner /></div>;
  if (!agent) return <p className="text-muted-foreground">Agent not found.</p>;

  const prompt = agent.system_prompt ?? "";
  const showToggle = prompt.length > 300;
  const displayPrompt = showToggle && !expanded ? prompt.slice(0, 300) + "…" : prompt;

  return (
    <div>
      <Link to="/agents" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back to Agents
      </Link>
      <PageHeader title={agent.name} description={agent.version ? `v${agent.version}` : undefined} />

      <Card className="mb-6 p-5 space-y-3 text-sm">
        {agent.description && <p>{agent.description}</p>}
        {agent.model_name && <p>Model: <Badge variant="outline">{agent.model_name}</Badge></p>}
        {prompt && (
          <div>
            <p className="text-muted-foreground mb-1">System Prompt:</p>
            <pre className="whitespace-pre-wrap text-xs bg-muted/30 rounded p-3">{displayPrompt}</pre>
            {showToggle && <button onClick={() => setExpanded(!expanded)} className="text-xs text-primary mt-1">{expanded ? "Show less" : "Show more"}</button>}
          </div>
        )}
        {agent.goal_templates?.length > 0 && (
          <div>
            <p className="text-muted-foreground mb-1">Goal Template:</p>
            <ul className="list-disc pl-5 text-xs space-y-1">
              {agent.goal_templates.map((t: any) => (
                <li key={t.id ?? t.title}>
                  {t.title}
                  {t.sections?.length > 0 && (
                    <ul className="list-[circle] pl-4 mt-1 space-y-0.5">
                      {t.sections.map((s: any, i: number) => <li key={i}>{s.heading ?? s.content}</li>)}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {agent.mcp_links?.length > 0 && (
          <div className="flex items-center gap-1 flex-wrap">
            Linked MCPs: {agent.mcp_links.map((l: any) => <Badge key={l.mcp_id ?? l.id} variant="outline">{l.mcp_name ?? l.mcp_id}</Badge>)}
          </div>
        )}
      </Card>

      {metrics && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard title="Downloads" value={formatNumber(metrics.downloads ?? 0)} icon={<Download className="h-4 w-4" />} />
          <StatCard title="Interactions" value={formatNumber(metrics.interactions ?? 0)} icon={<Activity className="h-4 w-4" />} />
          <StatCard title="Acceptance Rate" value={`${((metrics.acceptance_rate ?? 0) * 100).toFixed(0)}%`} icon={<CheckCircle className="h-4 w-4" />} />
          <StatCard title="Avg Latency" value={formatDuration(metrics.avg_latency_ms ?? 0)} icon={<Clock className="h-4 w-4" />} />
        </div>
      )}
    </div>
  );
}
