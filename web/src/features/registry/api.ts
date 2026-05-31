// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { get, post, put, del, patch } from "@/shared/api-client";
import type {
	RegistryItem,
	ValidationResult,
	VersionSuggestions,
	AgentVersionsResponse,
	ComponentVersionsResponse,
	ComponentVersionDetail,
	VersionDiff,
	RegistryType,
} from "./types";

export type { RegistryType } from "./types";

export const registry = {
	list: (type: RegistryType, params?: Record<string, string>) => {
		const qs = params ? `?${new URLSearchParams(params)}` : "";
		return get<RegistryItem[]>(`/${type}${qs}`);
	},
	get: (type: RegistryType, id: string) => get<RegistryItem>(`/${type}/${id}`),
	create: (type: RegistryType, body: unknown) =>
		post<RegistryItem>(`/${type}`, body),
	install: (type: RegistryType, id: string, body?: unknown) =>
		post<unknown>(`/${type}/${id}/install`, body),
	delete: (type: RegistryType, id: string) => del(`/${type}/${id}`),
	metrics: (type: RegistryType, id: string) =>
		get<unknown>(`/${type}/${id}/metrics`),
	resolve: (id: string) => get<unknown>(`/agents/${id}/resolve`),
	manifest: (id: string) =>
		get<Record<string, unknown>>(`/agents/${id}/manifest`),
	downloads: (id: string) =>
		get<{ total: number; unique_users: number; recent_7d: number }>(
			`/agents/${id}/downloads`,
		),
	validate: (body: {
		components: { component_type: string; component_id: string }[];
	}) => post<ValidationResult>("/agents/validate", body),
	previewConfig: (body: {
		name: string;
		description: string;
		prompt: string;
		model_name: string;
		components: { component_type: string; component_id: string }[];
		target_ides?: string[];
	}) =>
		post<{ configs: Record<string, Record<string, string>> }>(
			"/agents/preview-config",
			body,
		),
	my: (type?: RegistryType) => get<RegistryItem[]>(`/${type ?? "agents"}/my`),
	archived: () => get<RegistryItem[]>("/agents/archived"),
	archive: (id: string) => patch(`/agents/${id}/archive`),
	unarchive: (id: string) => patch(`/agents/${id}/unarchive`),
	draft: (body: unknown, type?: RegistryType) =>
		post<RegistryItem>(`/${type ?? "agents"}/draft`, body),
	updateDraft: (id: string, body: unknown, type?: RegistryType) =>
		put<RegistryItem>(`/${type ?? "agents"}/${id}/draft`, body),
	updateAgent: (id: string, body: unknown) =>
		put<RegistryItem>(`/agents/${id}`, body),
	submitDraft: (id: string, type?: RegistryType) =>
		post(`/${type ?? "agents"}/${id}/submit`),
	submit: (type: RegistryType, body: unknown) =>
		post<RegistryItem>(`/${type}/submit`, body),
	versionSuggestions: (id: string) =>
		get<VersionSuggestions>(`/agents/${id}/version-suggestions`),
	listVersions: (agentId: string, page = 1, pageSize = 50) =>
		get<AgentVersionsResponse>(
			`/agents/${agentId}/versions?page=${page}&page_size=${pageSize}`,
		),
	getVersion: (agentId: string, version: string) =>
		get<unknown>(`/agents/${agentId}/versions/${version}`),
	createVersion: (agentId: string, body: unknown) =>
		post<unknown>(`/agents/${agentId}/versions`, body),
	getVersionDiff: (agentId: string, v1: string, v2: string) =>
		get<VersionDiff>(`/agents/${agentId}/versions/${v1}/diff/${v2}`),
	listComponentVersions: (
		type: RegistryType,
		listingId: string,
		page = 1,
		pageSize = 50,
	) =>
		get<ComponentVersionsResponse>(
			`/${type}/${listingId}/versions?page=${page}&page_size=${pageSize}`,
		),
	getComponentVersion: (
		type: RegistryType,
		listingId: string,
		version: string,
	) => get<ComponentVersionDetail>(`/${type}/${listingId}/versions/${version}`),
	publishComponentVersion: (
		type: RegistryType,
		listingId: string,
		body: unknown,
	) => post<ComponentVersionDetail>(`/${type}/${listingId}/versions`, body),
	componentVersionSuggestions: (type: RegistryType, listingId: string) =>
		get<VersionSuggestions>(`/${type}/${listingId}/version-suggestions`),
	startEdit: (id: string, type?: RegistryType) =>
		post<{ status: string }>(`/${type ?? "agents"}/${id}/start-edit`),
	cancelEdit: (id: string, type?: RegistryType) =>
		post<{ status: string }>(`/${type ?? "agents"}/${id}/cancel-edit`),
};
