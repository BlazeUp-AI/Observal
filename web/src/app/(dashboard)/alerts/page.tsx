"use client";

import { useState } from "react";
import { Bell, Plus, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/layouts/page-header";
import { DashboardShell, DashboardContent } from "@/components/layouts/dashboard-shell";
import { NoData } from "@/components/dashboard/no-data";
import { StatusBadge } from "@/components/registry/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";
import { useAlerts, useCreateAlert, useUpdateAlert, useDeleteAlert } from "@/hooks/use-api";
import type { AlertRule } from "@/lib/types";

export default function AlertsPage() {
  const { data: alerts, isLoading } = useAlerts();
  const createAlert = useCreateAlert();
  const updateAlert = useUpdateAlert();
  const deleteAlert = useDeleteAlert();

  const [open, setOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [metric, setMetric] = useState<AlertRule["metric"]>("error_rate");
  const [threshold, setThreshold] = useState("");
  const [condition, setCondition] = useState<AlertRule["condition"]>("above");
  const [targetType, setTargetType] = useState<AlertRule["target_type"]>("all");
  const [targetId, setTargetId] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");

  const handleCreate = () => {
    createAlert.mutate(
      { name, metric, threshold: Number(threshold), condition, target_type: targetType, target_id: targetType === "all" ? "" : targetId, webhook_url: webhookUrl },
      { onSuccess: () => { setOpen(false); setName(""); setThreshold(""); setTargetId(""); setWebhookUrl(""); } },
    );
  };

  const toggleStatus = (a: AlertRule) => {
    updateAlert.mutate({ id: a.id, status: a.status === "active" ? "paused" : "active" });
  };

  const confirmDelete = () => {
    if (deleteId) deleteAlert.mutate(deleteId, { onSuccess: () => setDeleteId(null) });
  };

  const items = alerts ?? [];

  return (
    <DashboardShell>
      <PageHeader
        title="Alerts"
        actionButtonsRight={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm"><Plus className="h-3.5 w-3.5" /> Create Alert</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create Alert Rule</DialogTitle>
                <DialogDescription>Get notified when a metric crosses a threshold.</DialogDescription>
              </DialogHeader>
              <div className="grid gap-3 py-2">
                <div className="grid gap-1.5">
                  <Label>Name</Label>
                  <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="High error rate" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label>Metric</Label>
                    <Select value={metric} onValueChange={(v) => setMetric(v as AlertRule["metric"])}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="error_rate">Error Rate</SelectItem>
                        <SelectItem value="latency_p99">Latency P99</SelectItem>
                        <SelectItem value="token_usage">Token Usage</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Condition</Label>
                    <Select value={condition} onValueChange={(v) => setCondition(v as AlertRule["condition"])}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="above">Above</SelectItem>
                        <SelectItem value="below">Below</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-1.5">
                  <Label>Threshold</Label>
                  <Input type="number" value={threshold} onChange={(e) => setThreshold(e.target.value)} placeholder="0.05" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label>Target Type</Label>
                    <Select value={targetType} onValueChange={(v) => setTargetType(v as AlertRule["target_type"])}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="mcp">MCP Server</SelectItem>
                        <SelectItem value="agent">Agent</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {targetType !== "all" && (
                    <div className="grid gap-1.5">
                      <Label>Target ID</Label>
                      <Input value={targetId} onChange={(e) => setTargetId(e.target.value)} placeholder="UUID" />
                    </div>
                  )}
                </div>
                <div className="grid gap-1.5">
                  <Label>Webhook URL</Label>
                  <Input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://hooks.example.com/alert" />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                <Button onClick={handleCreate} disabled={!name || !threshold || createAlert.isPending}>
                  {createAlert.isPending ? "Creating…" : "Create"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />
      <DashboardContent>
        {isLoading ? (
          <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        ) : items.length === 0 ? (
          <NoData
            noDataText="No alert rules configured."
            description="Create one to get notified when metrics exceed thresholds."
          >
            <Bell className="mx-auto mt-2 h-8 w-8 text-muted-foreground/40" />
          </NoData>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="h-9 px-3 text-xs">Name</TableHead>
                  <TableHead className="h-9 px-3 text-xs">Metric</TableHead>
                  <TableHead className="h-9 px-3 text-xs">Condition</TableHead>
                  <TableHead className="h-9 px-3 text-xs">Threshold</TableHead>
                  <TableHead className="h-9 px-3 text-xs">Target</TableHead>
                  <TableHead className="h-9 px-3 text-xs">Status</TableHead>
                  <TableHead className="h-9 px-3 text-xs">Last Triggered</TableHead>
                  <TableHead className="h-9 w-20 px-3 text-xs" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="px-3 py-2 text-sm font-medium">{a.name}</TableCell>
                    <TableCell className="px-3 py-2 text-xs">{a.metric.replace("_", " ")}</TableCell>
                    <TableCell className="px-3 py-2 text-xs">{a.condition}</TableCell>
                    <TableCell className="px-3 py-2 text-sm">{a.threshold}</TableCell>
                    <TableCell className="px-3 py-2 text-xs">{a.target_type === "all" ? "All" : `${a.target_type}: ${a.target_id.slice(0, 8)}…`}</TableCell>
                    <TableCell className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Switch checked={a.status === "active"} onCheckedChange={() => toggleStatus(a)} />
                        <StatusBadge status={a.status} />
                      </div>
                    </TableCell>
                    <TableCell className="px-3 py-2 text-xs text-muted-foreground">
                      {a.last_triggered ? format(new Date(a.last_triggered), "MMM d, HH:mm") : "Never"}
                    </TableCell>
                    <TableCell className="px-3 py-2">
                      <Button variant="ghost" size="icon" onClick={() => setDeleteId(a.id)}>
                        <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Delete confirmation */}
        <Dialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete Alert Rule</DialogTitle>
              <DialogDescription>This action cannot be undone.</DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
              <Button variant="destructive" onClick={confirmDelete} disabled={deleteAlert.isPending}>
                {deleteAlert.isPending ? "Deleting…" : "Delete"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </DashboardContent>
    </DashboardShell>
  );
}
