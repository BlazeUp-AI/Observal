"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { AgentCard } from "@/components/registry/agent-card";
import { useRegistryList, useTopAgents } from "@/hooks/use-api";
import { useRouter } from "next/navigation";

export default function RegistryHome() {
  const [search, setSearch] = useState("");
  const router = useRouter();
  const { data: agents } = useRegistryList("agents");
  const { data: topAgents } = useTopAgents();

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
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Agent Registry</h1>
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

      {trending.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">Trending</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {trending.map((item: any) => (
              <AgentCard
                key={item.id}
                id={item.id}
                name={item.name}
                downloads={item.value}
              />
            ))}
          </div>
        </section>
      )}

      {topRated.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">Top Rated</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
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
        </section>
      )}
    </div>
  );
}
