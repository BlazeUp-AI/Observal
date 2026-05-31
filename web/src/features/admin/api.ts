// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { get, post, put, del } from "@/shared/api-client";
import type {
	AdminUser,
	AdminSetting,
	TelemetryStatus,
	AuditLogEntry,
	SecurityEvent,
	DiagnosticsResponse,
	SystemWarning,
	RetentionConfig,
	RetentionConfigUpdate,
	RetentionPreview,
	RetentionStats,
	RetentionWarnings,
	PublicConfig,
	IdeEntry,
} from "./types";
import type { BulkResult } from "@/features/registry/types";
import { getAccessToken } from "@/shared/api-client";

export const telemetry = {
	status: () => get<TelemetryStatus>("/telemetry/status"),
	ingest: (body: unknown) => post<unknown>("/telemetry/ingest", body),
};

export const admin = {
	settings: () =>
		get<AdminSetting[] | Record<string, string>>("/admin/settings"),
	updateSetting: (key: string, body: unknown) =>
		put<unknown>(`/admin/settings/${key}`, body),
	deleteSetting: (key: string) => del(`/admin/settings/${key}`),
	revokeSetting: (key: string) =>
		post<{ revoked: string; message: string }>(
			`/admin/settings/${key}/revoke`,
			{},
		),
	users: () => get<AdminUser[]>("/admin/users"),
	createUser: (body: {
		email: string;
		name: string;
		username?: string;
		role?: string;
	}) =>
		post<{
			id: string;
			email: string;
			name: string;
			username?: string;
			role: string;
			password: string;
		}>("/admin/users", body),
	updateRole: (id: string, body: { role: string }) =>
		put<AdminUser>(`/admin/users/${id}/role`, body),
	updateDepartment: (id: string, body: { department: string | null }) =>
		put<AdminUser>(`/admin/users/${id}/department`, body),
	bulkDepartment: (entries: { email: string; department: string }[]) =>
		post<{ updated: number; not_found: string[] }>(
			"/admin/users/bulk-department",
			{ entries },
		),
	resetPassword: (
		id: string,
		body: { new_password?: string; generate?: boolean },
	) =>
		put<{
			message: string;
			generated_password?: string;
			must_change_password?: string;
		}>(`/admin/users/${id}/password`, body),
	deleteUser: (id: string) => del(`/admin/users/${id}`),
	applyResources: () =>
		post<{ applied: Record<string, string>; message: string }>(
			"/admin/resources/apply",
			{},
		),
	getTracePrivacy: () =>
		get<{ trace_privacy: boolean }>("/admin/org/trace-privacy"),
	setTracePrivacy: (enabled: boolean) =>
		put<{ trace_privacy: boolean }>("/admin/org/trace-privacy", {
			trace_privacy: enabled,
		}),
	getRegisteredAgentsOnly: () =>
		get<{ registered_agents_only: boolean }>(
			"/admin/org/registered-agents-only",
		),
	setRegisteredAgentsOnly: (enabled: boolean) =>
		put<{ registered_agents_only: boolean }>(
			"/admin/org/registered-agents-only",
			{ registered_agents_only: enabled },
		),
	auditLog: (params?: Record<string, string>) => {
		const qs = params ? `?${new URLSearchParams(params)}` : "";
		return get<AuditLogEntry[]>(`/admin/audit-log${qs}`);
	},
	auditLogExport: async (params?: Record<string, string>) => {
		const qs = params ? `?${new URLSearchParams(params)}` : "";
		const token = getAccessToken();
		const headers: Record<string, string> = {};
		if (token) headers["Authorization"] = `Bearer ${token}`;
		const res = await fetch(`/api/v1/admin/audit-log/export${qs}`, { headers });
		if (!res.ok) throw new Error("Export failed");
		return res.text();
	},
	securityEvents: (params?: Record<string, string>) => {
		const qs = params ? `?${new URLSearchParams(params)}` : "";
		return get<{ events: SecurityEvent[]; total: number }>(
			`/admin/security-events${qs}`,
		);
	},
	diagnostics: () => get<DiagnosticsResponse>("/admin/diagnostics"),
	systemWarnings: () => get<SystemWarning[]>("/admin/system-warnings"),
	samlConfig: () => get<Record<string, unknown>>("/admin/saml-config"),
	updateSamlConfig: (body: Record<string, unknown>) =>
		put<Record<string, unknown>>("/admin/saml-config", body),
	deleteSamlConfig: () => del("/admin/saml-config"),
	scimTokens: () =>
		get<
			{
				id: string;
				description: string;
				active: boolean;
				created_at: string;
				token_prefix: string;
			}[]
		>("/admin/scim-tokens"),
	createScimToken: (body: { description?: string }) =>
		post<{ id: string; token: string; description: string; message: string }>(
			"/admin/scim-tokens",
			body,
		),
	revokeScimToken: (id: string) => del(`/admin/scim-tokens/${id}`),
	getRetention: () => get<RetentionConfig>("/admin/org/retention"),
	setRetention: (body: RetentionConfigUpdate) =>
		put<RetentionConfig>("/admin/org/retention", body),
	previewRetention: (days: number) =>
		get<RetentionPreview>(`/admin/org/retention/preview?days=${days}`),
	getRetentionStats: () => get<RetentionStats>("/admin/org/retention/stats"),
	getRetentionWarnings: () =>
		get<RetentionWarnings>("/admin/org/retention/warnings"),
};

interface IdesResponse {
	ides: IdeEntry[];
}

export const config = {
	public: () => get<PublicConfig>("/config/public"),
	ides: () => get<IdesResponse>("/config/ides").then((r) => r.ides),
};

export const models = {
	list: () => get<import("./types").ModelCatalog>("/models"),
	refresh: () =>
		post<import("./types").ModelRefreshResult>("/admin/models/refresh"),
};

export const bulk = {
	createAgents: (body: { agents: unknown[]; dry_run?: boolean }) =>
		post<BulkResult>("/bulk/agents", body),
};

export const health = () => fetch("/health").then((r) => r.json());
