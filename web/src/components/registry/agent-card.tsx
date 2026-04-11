import Link from "next/link";
import { Bot } from "lucide-react";

interface AgentCardProps {
  id: string;
  name: string;
  description?: string;
  model_name?: string;
  owner?: string;
  downloads?: number;
  score?: number;
}

export function AgentCard({ id, name, description, model_name, owner, downloads, score }: AgentCardProps) {
  return (
    <Link
      href={`/agents/${id}`}
      className="block border border-border rounded-sm p-4 hover:bg-accent/50 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="font-medium text-sm">{name}</span>
        </div>
        {score != null && (
          <span className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded-sm">
            {score.toFixed(1)}
          </span>
        )}
      </div>
      {description && (
        <p className="mt-1.5 text-xs text-muted-foreground line-clamp-2">{description}</p>
      )}
      <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
        {model_name && <span>{model_name}</span>}
        {owner && <span>{owner}</span>}
        {downloads != null && <span>{downloads} pulls</span>}
      </div>
    </Link>
  );
}
