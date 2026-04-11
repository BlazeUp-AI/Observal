"use client";

import { useAdminSettings } from "@/hooks/use-api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function SettingsPage() {
  const { data: settings, isLoading } = useAdminSettings();

  const entries = Array.isArray(settings)
    ? settings.map((s: any) => [s.key, s.value])
    : Object.entries(settings ?? {});

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Key</TableHead>
            <TableHead>Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow><TableCell colSpan={2} className="text-center text-muted-foreground">Loading...</TableCell></TableRow>
          ) : entries.length === 0 ? (
            <TableRow><TableCell colSpan={2} className="text-center text-muted-foreground">No settings</TableCell></TableRow>
          ) : (
            entries.map(([key, value]: any) => (
              <TableRow key={key}>
                <TableCell className="font-mono text-sm">{key}</TableCell>
                <TableCell className="text-muted-foreground">{String(value)}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
