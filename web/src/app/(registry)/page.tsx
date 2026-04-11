"use client";

import { useState } from "react";
import { Search, Bot, TrendingUp } from "lucide-react";
import { Input } from "@/components/ui/input";
import { AgentCard } from "@/components/registry/agent-card";
import { useRegistryList, useTopAgents } from "@/hooks/use-api";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layouts/page-header";
import { CardSkeleton } from "@/components/shared/skeleton-layouts";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";

export default function RegistryHome() {
  const [search, setSearch] = useState("");
  const router = useRouter();
  const { data: agents, isLoading: agentsLoading, isError: agentsError, error: agentsErr, refetch: refetchAgents } = useRegistryList("agents");
  const { data: topAgents, isLoading: topLoading } = useTopAgents();

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (search.trim()) {
      router.push(`/agents?search=${encodeURIComponent(search.trim())}`);
    }
  }

  const trending = topAgents?.slice(0, 6) ?? [];
  const topRated = (agents ?? [])
    .filter((a: any) => a.status === "approved")
    .slice(0, 6);

  return (
    <>
      <PageHeader
        title="Agent Registry"
        breadcrumbs={[
          { label: "Registry" },
        ]}
      />
      <div className="p-6 max-w-6xl mx-auto space-y-8">
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Browse, install, and evaluate agents across your team.
          </p>
        </div>

        <form onSubmit={handleSearch} className="relative max-w-lg">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search agents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </form>

        <section>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">Trending</h2>
          {topLoading ? (
            <CardSkeleton count={3} columns={3} />
          ) : trending.length === 0 ? (
            <EmptyState
              icon={TrendingUp}
              title="No trending agents"
              description="Agents with the most downloads will appear here."
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {trending.map((item: any) => (
                <AgentCard
                  key={item.id}
                  id={item.id}
                  name={item.name}
                  downloads={item.value}
                />
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">Top Rated</h2>
          {agentsLoading ? (
            <CardSkeleton count={3} columns={3} />
          ) : agentsError ? (
            <ErrorState message={agentsErr?.message} onRetry={() => refetchAgents()} />
          ) : topRated.length === 0 ? (
            <EmptyState
              icon={Bot}
              title="No approved agents"
              description="Approved agents will appear here. Submit your first agent to get started."
              actionLabel="Submit an Agent"
              actionHref="/agents"
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {topRated.map((agent: any) => (
                <AgentCard
                  key={agent.id}
                  id={agent.id}
                  name={agent.name}
                  description={agent.description}
                  model_name={agent.model_name}
                  owner={agent.owner}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
