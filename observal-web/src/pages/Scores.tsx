import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui";
import { BarChart3 } from "lucide-react";

export default function Scores() {
  return (
    <div>
      <PageHeader title="Scores" />
      <EmptyState
        icon={<BarChart3 className="h-8 w-8" />}
        title="Score analytics coming soon"
        description="View and analyze scores across traces, including human ratings and LLM-as-judge evaluations."
      />
    </div>
  );
}
