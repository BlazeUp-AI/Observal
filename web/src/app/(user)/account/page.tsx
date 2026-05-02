"use client";

import { useState, useCallback, useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import { Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { getUserName, getUserEmail, getUserRole, auth } from "@/lib/api";
import { ROLE_LABELS, type Role } from "@/hooks/use-role-guard";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/layouts/page-header";

// ── Theme definitions ──────────────────────────────────────────────────────
// Swatches: [bg, accent, fg] in oklch — derived from globals.css
const THEMES = [
  { value: "light", label: "Light", swatches: ["oklch(0.99 0.005 260)", "oklch(0.5 0.2 270)", "oklch(0.15 0.02 260)"] },
  { value: "solarized-light", label: "Solarized Light", swatches: ["oklch(0.97 0.026 90)", "oklch(0.61 0.139 245)", "oklch(0.52 0.028 219)"] },
  { value: "dark", label: "Dark", swatches: ["oklch(0.13 0.02 260)", "oklch(0.62 0.18 270)", "oklch(0.88 0.01 260)"] },
  { value: "midnight", label: "Midnight", swatches: ["oklch(0.1 0.025 270)", "oklch(0.6 0.2 275)", "oklch(0.88 0.008 260)"] },
  { value: "forest", label: "Forest", swatches: ["oklch(0.1 0.02 155)", "oklch(0.6 0.15 155)", "oklch(0.87 0.01 150)"] },
  { value: "sunset", label: "Sunset", swatches: ["oklch(0.11 0.025 45)", "oklch(0.7 0.15 60)", "oklch(0.87 0.01 50)"] },
  { value: "solarized-dark", label: "Solarized Dark", swatches: ["oklch(0.27 0.049 220)", "oklch(0.61 0.139 245)", "oklch(0.65 0.020 205)"] },
  { value: "dracula", label: "Dracula", swatches: ["oklch(0.26 0.030 278)", "oklch(0.74 0.149 302)", "oklch(0.98 0.008 107)"] },
  { value: "nord", label: "Nord", swatches: ["oklch(0.30 0.018 230)", "oklch(0.78 0.065 205)", "oklch(0.93 0.010 230)"] },
  { value: "monokai", label: "Monokai", swatches: ["oklch(0.25 0.012 110)", "oklch(0.84 0.20 128)", "oklch(0.98 0.008 107)"] },
  { value: "gruvbox", label: "Gruvbox", swatches: ["oklch(0.28 0.000 90)", "oklch(0.73 0.182 52)", "oklch(0.88 0.055 85)"] },
  { value: "catppuccin", label: "Catppuccin", swatches: ["oklch(0.22 0.035 290)", "oklch(0.72 0.14 305)", "oklch(0.86 0.045 270)"] },
  { value: "tokyo-night", label: "Tokyo Night", swatches: ["oklch(0.20 0.025 260)", "oklch(0.68 0.15 260)", "oklch(0.76 0.050 268)"] },
  { value: "one-dark", label: "One Dark", swatches: ["oklch(0.27 0.012 240)", "oklch(0.70 0.13 240)", "oklch(0.78 0.018 250)"] },
  { value: "rose-pine", label: "Rosé Pine", swatches: ["oklch(0.19 0.030 300)", "oklch(0.74 0.10 305)", "oklch(0.90 0.028 295)"] },
] as const;

// ── localStorage sync helpers ──────────────────────────────────────────────
function subscribe(cb: () => void) {
  window.addEventListener("storage", cb);
  return () => window.removeEventListener("storage", cb);
}

function getNameSnapshot() {
  if (typeof window === "undefined") return "";
  return getUserName() ?? "";
}

function getEmailSnapshot() {
  if (typeof window === "undefined") return "";
  return getUserEmail() ?? "";
}

function getRoleSnapshot() {
  if (typeof window === "undefined") return "";
  return getUserRole() ?? "";
}

function getServerSnapshot() {
  return "";
}

function initials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

// ── Change Password ───────────────────────────────────────────────────────
function ChangePasswordSection() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (newPassword.length < 8) {
      toast.error("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }
    setSaving(true);
    try {
      await auth.changePassword({ current_password: currentPassword, new_password: newPassword });
      toast.success("Password changed successfully");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to change password");
    } finally {
      setSaving(false);
    }
  }, [currentPassword, newPassword, confirmPassword]);

  return (
    <section className="animate-in stagger-1">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        Change Password
      </h3>
      <Card>
        <CardContent className="p-4 space-y-3">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Current Password</label>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="h-8 text-sm"
              placeholder="Enter current password"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">New Password</label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="h-8 text-sm"
              placeholder="At least 8 characters"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Confirm New Password</label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="h-8 text-sm"
              placeholder="Re-enter new password"
              onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
            />
          </div>
          <Button
            size="sm"
            className="h-8"
            onClick={handleSubmit}
            disabled={saving || !currentPassword || !newPassword || !confirmPassword}
          >
            {saving ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Update Password
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function AccountPage() {
  const name = useSyncExternalStore(subscribe, getNameSnapshot, getServerSnapshot);
  const email = useSyncExternalStore(subscribe, getEmailSnapshot, getServerSnapshot);
  const role = useSyncExternalStore(subscribe, getRoleSnapshot, getServerSnapshot);

  const { theme, setTheme } = useTheme();

  const [agentUpdates, setAgentUpdates] = useState(false);
  const [reviewAssignments, setReviewAssignments] = useState(false);
  const [emailNotifications, setEmailNotifications] = useState(false);

  const displayName = name || "—";
  const displayEmail = email || "—";
  const roleLabel = role ? (ROLE_LABELS[role as Role] ?? role) : "—";

  return (
    <>
      <PageHeader title="Account" />
      <div className="p-6 w-full mx-auto max-w-2xl space-y-6">

        {/* ── Section 1: Profile ─────────────────────────────────────────── */}
        <section className="animate-in">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Profile
          </h3>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-4">
                <Avatar className="h-12 w-12 shrink-0">
                  <AvatarFallback className="text-sm font-semibold">
                    {initials(displayName)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold truncate">{displayName}</p>
                  <p className="text-xs text-muted-foreground truncate mt-0.5">{displayEmail}</p>
                </div>
                <Badge variant="secondary" className="shrink-0 text-xs">
                  {roleLabel}
                </Badge>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* ── Section 2: Change Password ───────────────────────────────── */}
        <ChangePasswordSection />

        {/* ── Section 3: Theme ───────────────────────────────────────────── */}
        <section className="animate-in stagger-1">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Theme
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {THEMES.map((t) => {
              const isActive = theme === t.value;
              return (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setTheme(t.value)}
                  className={
                    "rounded-md border p-3 text-left transition-colors hover:bg-accent/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" +
                    (isActive ? " border-primary-accent bg-accent/20" : " border-border bg-card")
                  }
                >
                  {/* Color preview: 3 stacked bars */}
                  <div className="rounded overflow-hidden mb-2.5 h-8 flex flex-col gap-px">
                    {t.swatches.map((color, i) => (
                      <div
                        key={i}
                        className="flex-1"
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium">{t.label}</span>
                    {isActive && (
                      <Check className="h-3 w-3 text-primary-accent" />
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        {/* ── Section 3: Notifications ───────────────────────────────────── */}
        <section className="animate-in stagger-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Notifications
          </h3>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle>Notification Preferences</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                Notification preferences will be saved in a future release.
              </p>
            </CardHeader>
            <CardContent className="p-4 pt-0 space-y-0">
              <div className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium">Agent update notifications</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Notify when a monitored agent completes or errors
                  </p>
                </div>
                <Switch
                  checked={agentUpdates}
                  onCheckedChange={setAgentUpdates}
                  disabled
                  aria-label="Agent update notifications"
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium">Review assignment notifications</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Notify when a trace is assigned to you for review
                  </p>
                </div>
                <Switch
                  checked={reviewAssignments}
                  onCheckedChange={setReviewAssignments}
                  disabled
                  aria-label="Review assignment notifications"
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium">Email notifications</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Receive the above notifications by email
                  </p>
                </div>
                <Switch
                  checked={emailNotifications}
                  onCheckedChange={setEmailNotifications}
                  disabled
                  aria-label="Email notifications"
                />
              </div>
            </CardContent>
          </Card>
        </section>

      </div>
    </>
  );
}
