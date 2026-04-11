"use client";

import { use } from "react";
import { FlaskConical } from "lucide-react";
import { useEvalScorecards, useEvalAggregate, useRegistryItem, useEvalRun, useEvalPenalties } from "@/hooks/use-api";
import { AgentAggregateChart } from "@/components/dashboard/agent-aggregate-chart";
import { DimensionRadar } from "@/components/dashboard/dimension-radar";
import { PenaltyAccordion } from "@/components/dashboard/penalty-accordion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layouts/page-header";
import { DetailSkeleton, TableSkeleton, ChartSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

export default function EvalDetailPage({ params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = use(params);
  const { data: agent } = useRegistryItem("agents", agentId);
  const { data: scorecards, isLoading, isError, error, refetch } = useEvalScorecards(agentId);
  const { data: aggregate, isLoading: aggLoading } = useEvalAggregate(agentId);
  const runEval = useEvalRun();

  const a = agent as any;
  const cards = scorecards ?? [];
  const latest = cards[0];

  const { data: latestPenalties } = useEvalPenalties(latest?.id);

  const agentName = a?.name ?? agentId.slice(0, 8);

  return (
    <>
      <PageHeader
        title={agentName}
        breadcrumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Eval", href: "/eval" },
          { label: agentName },
        ]}
        actionButtonsRight={
          <Button
            size="sm"
            onClick={() => runEval.mutate({ agentId })}
            disabled={runEval.isPending}
          >
            {runEval.isPending ? "Running..." : "Run Eval"}
          </Button>
        }
      />
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {aggLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ChartSkeleton />
            <ChartSkeleton />
          </div>
        ) : aggregate ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <h2 className="text-sm font-medium text-muted-foreground mb-3">Score Over Time</h2>
              <AgentAggregateChart data={aggregate} />
            </div>
            {latest?.dimension_scores && (
              <div>
                <h2 className="text-sm font-medium text-muted-foreground mb-3">Latest Dimensions</h2>
                <DimensionRadar dimensionScores={latest.dimension_scores} />
              </div>
            )}
          </div>
        ) : null}

        {latest && (
          <section>
            <h2 className="text-sm font-medium text-muted-foreground mb-3">Latest Scorecard</h2>
            <div className="border border-border rounded-sm p-4 space-y-2">
              <div className="flex items-center gap-3">
                {latest.grade && <Badge variant="default">{latest.grade}</Badge>}
                {latest.display_score != null && <span className="text-sm font-mono">{latest.display_score.toFixed(1)}/10</span>}
                {latest.version && <span className="text-xs text-muted-foreground">v{latest.version}</span>}
              </div>
              {(latest.scoring_recommendations ?? []).length > 0 && (
                <ul className="text-xs text-muted-foreground space-y-1">
                  {(latest.scoring_recommendations ?? []).map((r: string, i: number) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        )}

        {latestPenalties && latestPenalties.length > 0 && (
          <section>
            <h2 className="text-sm font-medium text-muted-foreground mb-3">Penalties</h2>
            <PenaltyAccordion penalties={latestPenalties} />
          </section>
        )}

        <section>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">Scorecard History</h2>
          {isLoading ? (
            <TableSkeleton rows={5} cols={5} />
          ) : isError ? (
            <ErrorState message={error?.message} onRetry={() => refetch()} />
          ) : cards.length === 0 ? (
            <EmptyState
              icon={FlaskConical}
              title="No scorecards yet"
              description="Run an eval to generate scores for this agent."
              onAction={() => runEval.mutate({ agentId })}
              actionLabel="Run Eval"
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>Grade</TableHead>
                    <TableHead>Penalties</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {cards.map((sc: any) => (
                    <TableRow key={sc.id}>
                      <TableCell className="text-xs">{sc.created_at ? new Date(sc.created_at).toLocaleDateString() : "-"}</TableCell>
                      <TableCell className="text-muted-foreground">{sc.version ?? "-"}</TableCell>
                      <TableCell className="font-mono">{sc.display_score?.toFixed(1) ?? sc.overall_score?.toFixed(1) ?? "-"}</TableCell>
                      <TableCell><Badge variant="outline">{sc.grade ?? sc.overall_grade ?? "-"}</Badge></TableCell>
                      <TableCell className="text-muted-foreground">{sc.penalty_count ?? 0}</TableCell>
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
