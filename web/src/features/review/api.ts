// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { get, post } from "@/shared/api-client";
import type { ReviewItem } from "@/features/registry/types";

export const review = {
	list: (params?: Record<string, string>) => {
		const qs = params ? `?${new URLSearchParams(params)}` : "";
		return get<ReviewItem[]>(`/review${qs}`);
	},
	listAgents: () => get<ReviewItem[]>("/review?tab=agents"),
	get: (id: string) => get<ReviewItem>(`/review/${id}`),
	approve: (id: string) => post(`/review/${id}/approve`),
	reject: (id: string, body: { reason: string }) =>
		post(`/review/${id}/reject`, body),
	approveAgent: (id: string, body?: { category?: string }) =>
		post(`/review/agents/${id}/approve`, body),
	rejectAgent: (id: string, body: { reason: string }) =>
		post(`/review/agents/${id}/reject`, body),
	approveBundle: (id: string) => post(`/review/bundles/${id}/approve`),
	rejectBundle: (id: string, body: { reason: string }) =>
		post(`/review/bundles/${id}/reject`, body),
	relatedSkills: (id: string) =>
		get<{ skills: ReviewItem[] }>(`/review/${id}/related-skills`),
	approveWithSkills: (id: string, body: { skill_ids: string[] }) =>
		post(`/review/${id}/approve-with-skills`, body),
};
