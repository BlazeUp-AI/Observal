// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { get, post, put } from "@/shared/api-client";
import type {
	OverviewStats,
	TopItem,
	TrendPoint,
	TokenStats,
	IdeUsageData,
} from "@/features/dashboard/types";
import type {
	TopAgentItem,
	LeaderboardItem,
	LeaderboardWindow,
	ComponentLeaderboardItem,
} from "@/features/registry/types";
import type {
	SessionsStats,
	SessionTrace,
	SessionData,
	Session,
	SessionsSummary,
	SessionErrorEvent,
} from "@/features/traces/types";
import type {
	ExecAdoptionResponse,
	ExecAgentCounts,
	ExecUsageByCategory,
	ExecPlatformCoverage,
	ExecPlatformScore,
	ExecVelocityResponse,
	ExecTopAgent,
	ExecConfig,
	ExecDepartmentsResponse,
	ExecDeptTokenItem,
	ExecCostSummary,
	ExecROIProjectionsResponse,
	ExecStrategicInsightsResponse,
	ExecDeveloperBreakdown,
	ExecInactivityAlerts,
	ExecTimeToValueResponse,
	ExecAIInsightsResponse,
} from "@/features/admin/types";

export const dashboard = {
	stats: (range?: string) =>
		get<OverviewStats>(`/overview/stats${range ? `?range=${range}` : ""}`),
	topMcps: () => get<TopItem[]>("/overview/top-mcps"),
	topAgents: (limit?: number) =>
		get<TopAgentItem[]>(
			`/overview/top-agents${limit ? `?limit=${limit}` : ""}`,
		),
	leaderboard: (window?: LeaderboardWindow, limit?: number, user?: string) => {
		const params = new URLSearchParams();
		if (window) params.set("window", window);
		if (limit) params.set("limit", String(limit));
		if (user) params.set("user", user);
		const qs = params.toString();
		return get<LeaderboardItem[]>(`/overview/leaderboard${qs ? `?${qs}` : ""}`);
	},
	componentLeaderboard: (window?: LeaderboardWindow, limit?: number) => {
		const params = new URLSearchParams();
		if (window) params.set("window", window);
		if (limit) params.set("limit", String(limit));
		const qs = params.toString();
		return get<ComponentLeaderboardItem[]>(
			`/overview/component-leaderboard${qs ? `?${qs}` : ""}`,
		);
	},
	trends: (range?: string) =>
		get<TrendPoint[]>(`/overview/trends${range ? `?range=${range}` : ""}`),
	tokenStats: (range?: string) =>
		get<TokenStats>(`/dashboard/tokens${range ? `?range=${range}` : ""}`),
	ideUsage: () => get<IdeUsageData>("/dashboard/ide-usage"),
	sessions: (params?: {
		status?: string;
		platform?: string;
		days?: number;
		limit?: number;
		offset?: number;
	}) => {
		const qs = new URLSearchParams();
		if (params?.status) qs.set("status", params.status);
		if (params?.platform) qs.set("platform", params.platform);
		if (params?.days) qs.set("days", String(params.days));
		if (params?.limit) qs.set("limit", String(params.limit));
		if (params?.offset) qs.set("offset", String(params.offset));
		const suffix = qs.toString() ? `?${qs}` : "";
		return get<Session[]>(`/sessions${suffix}`);
	},
	sessionsSummary: () => get<SessionsSummary>("/sessions/summary"),
	session: (id: string) =>
		get<SessionData>(`/sessions/${encodeURIComponent(id)}`),
	traces: () => get<SessionTrace[]>("/sessions/traces"),
	trace: (id: string) =>
		get<unknown>(`/sessions/traces/${encodeURIComponent(id)}`),
	sessionsStats: () => get<SessionsStats>("/sessions/stats"),
	sessionsErrors: () => get<SessionErrorEvent[]>("/sessions/errors"),
};

export const exec = {
	adoption: () => get<ExecAdoptionResponse>("/exec/adoption"),
	agentCounts: () => get<ExecAgentCounts>("/exec/agent-counts"),
	usageByCategory: (range?: string) =>
		get<ExecUsageByCategory[]>(
			`/exec/usage-by-category${range ? `?range=${range}` : ""}`,
		),
	platformCoverage: () =>
		get<ExecPlatformCoverage[]>("/exec/platform-coverage"),
	platforms: () => get<ExecPlatformScore[]>("/exec/platforms"),
	velocity: () => get<ExecVelocityResponse>("/exec/velocity"),
	topAgents: (limit?: number) =>
		get<ExecTopAgent[]>(`/exec/top-agents${limit ? `?limit=${limit}` : ""}`),
	departments: (range?: string) =>
		get<ExecDepartmentsResponse>(
			`/exec/departments${range ? `?range=${range}` : ""}`,
		),
	deptTokens: (range?: string) =>
		get<ExecDeptTokenItem[]>(
			`/exec/dept-tokens${range ? `?range=${range}` : ""}`,
		),
	costSummary: (range?: string) =>
		get<ExecCostSummary>(`/exec/cost-summary${range ? `?range=${range}` : ""}`),
	roiProjections: () =>
		get<ExecROIProjectionsResponse>("/exec/roi-projections"),
	strategicInsights: () =>
		get<ExecStrategicInsightsResponse>("/exec/strategic-insights"),
	developerBreakdown: (limit?: number) =>
		get<ExecDeveloperBreakdown>(
			`/exec/developer-breakdown${limit ? `?limit=${limit}` : ""}`,
		),
	inactivityAlerts: () => get<ExecInactivityAlerts>("/exec/inactivity-alerts"),
	timeToValue: () => get<ExecTimeToValueResponse>("/exec/time-to-value"),
	aiInsights: () => get<ExecAIInsightsResponse>("/exec/ai-insights"),
	config: () => get<ExecConfig | null>("/exec/config"),
	updateConfig: (data: Partial<ExecConfig>) =>
		put<ExecConfig>("/exec/config", data),
};
