import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui";
import { FlaskConical } from "lucide-react";

export default function Evaluations() {
  return (
    <div>
      <PageHeader title="Evaluations" />
      <EmptyState
        icon={<FlaskConical className="h-8 w-8" />}
        title="No evaluations yet"
        description="Run evaluations from the CLI: observal eval run <agent-id>"
      />
    </div>
  );
}
