"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const IDES = [
  { value: "cursor", label: "Cursor" },
  { value: "vscode", label: "VS Code" },
  { value: "claude-code", label: "Claude Code" },
  { value: "gemini-cli", label: "Gemini CLI" },
  { value: "kiro", label: "Kiro" },
  { value: "codex", label: "Codex" },
  { value: "copilot", label: "Copilot" },
];

export function PullCommand({ agentName }: { agentName: string }) {
  const [ide, setIde] = useState("cursor");
  const [copied, setCopied] = useState(false);

  const command = `observal pull ${agentName} --ide ${ide}`;

  function handleCopy() {
    navigator.clipboard.writeText(command);
    setCopied(true);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="border border-border rounded-sm bg-muted/30">
      <div className="flex items-center gap-2 p-3">
        <Select value={ide} onValueChange={setIde}>
          <SelectTrigger className="w-[140px] h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {IDES.map((i) => (
              <SelectItem key={i.value} value={i.value}>{i.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <code className="flex-1 text-sm font-mono bg-background px-3 py-1.5 rounded-sm border border-border select-all">
          {command}
        </code>
        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={handleCopy}>
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </Button>
      </div>
    </div>
  );
}
