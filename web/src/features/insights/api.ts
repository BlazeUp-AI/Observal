// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { get, post } from "@/shared/api-client";
import type { FeedbackItem, FeedbackSummary } from "@/features/registry/types";
import type {
	InsightReportListItem,
	InsightReport,
	InsightAppliedItems,
} from "@/features/admin/types";
import { getAccessToken } from "@/shared/api-client";

export const feedback = {
	submit: (body: {
		listing_type: string;
		listing_id: string;
		rating: number;
		comment?: string;
	}) => post<FeedbackItem>("/feedback", body),
	get: (type: string, id: string) =>
		get<FeedbackItem[]>(`/feedback/${type}/${id}`),
	summary: (id: string) => get<FeedbackSummary>(`/feedback/summary/${id}`),
};

export const insights = {
	status: () => get<{ available: boolean; reason: string | null }>("/insights/status"),
	sessionCount: (agentId: string) => get<{ session_count: number }>(`/insights/agents/${agentId}/session-count`),
	generate: (agentId: string, periodDays?: number) =>
		post<InsightReportListItem>(
			`/insights/agents/${agentId}/generate`,
			periodDays ? { period_days: periodDays } : {},
		),
	listReports: (agentId: string) =>
		get<InsightReportListItem[]>(`/insights/agents/${agentId}/reports`),
	getReport: (reportId: string) =>
		get<InsightReport>(`/insights/reports/${reportId}`),
	applySuggestions: (reportId: string, selection?: { config_indices?: number[]; feature_indices?: number[]; pattern_indices?: number[] }) =>
		post<{ applied: boolean; report_id: string; items: InsightAppliedItems }>(
			`/insights/reports/${reportId}/apply`,
			selection ?? {},
		),
	exportHtml: async (reportId: string): Promise<void> => {
		const token = getAccessToken();
		const res = await fetch(`/api/v1/insights/reports/${reportId}/export/html`, {
			headers: token ? { Authorization: `Bearer ${token}` } : {},
		});
		if (!res.ok) throw new Error("Export failed");
		const blob = await res.blob();
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = `insight-report-${reportId.slice(0, 8)}.html`;
		a.click();
		URL.revokeObjectURL(url);
	},
};

export const models = {
	list: () => get<import("@/features/admin/types").ModelCatalog>("/models"),
	refresh: () =>
		post<import("@/features/admin/types").ModelRefreshResult>("/admin/models/refresh"),
};
