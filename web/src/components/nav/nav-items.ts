// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import {
	Home,
	Bot,
	Blocks,
	Hammer,
	Trophy,
	LayoutDashboard,
	Activity,
	ShieldCheck,
	Users,
	Settings,
	ScrollText,
	ShieldAlert,
	Stethoscope,
	KeyRound,
	Lightbulb,
} from "lucide-react";
import type { Role } from "@/shared/hooks/use-role-guard";

export type NavItem = {
	title: string;
	href: string;
	icon: typeof Home;
	requiresAuth?: boolean;
	minRole?: Role;
	requiresFeature?: string;
};

export const registryNav: NavItem[] = [
	{ title: "Home", href: "/", icon: Home },
	{ title: "Agents", href: "/agents", icon: Bot },
	{ title: "Leaderboard", href: "/leaderboard", icon: Trophy },
	{ title: "Components", href: "/components", icon: Blocks },
	{
		title: "Builder",
		href: "/agents/builder",
		icon: Hammer,
		requiresAuth: true,
	},
];

export const reviewNav: NavItem[] = [
	{ title: "Review", href: "/review", icon: ShieldCheck, minRole: "reviewer" },
];

export const userNav: NavItem[] = [
	{ title: "My Traces", href: "/traces", icon: Activity, minRole: "user" },
];

export const adminNav: NavItem[] = [
	{
		title: "Dashboard",
		href: "/dashboard",
		icon: LayoutDashboard,
		minRole: "admin",
		requiresFeature: "exec_dashboard",
	},
	{
		title: "Insights",
		href: "/insights",
		icon: Lightbulb,
		minRole: "admin",
		requiresFeature: "insights",
	},
	{ title: "Users", href: "/users", icon: Users, minRole: "admin" },
	{
		title: "Audit Log",
		href: "/audit-log",
		icon: ScrollText,
		minRole: "admin",
		requiresFeature: "audit",
	},
	{
		title: "Security",
		href: "/security-events",
		icon: ShieldAlert,
		minRole: "admin",
		requiresFeature: "security_events",
	},
	{
		title: "SSO & SCIM",
		href: "/sso",
		icon: KeyRound,
		minRole: "admin",
		requiresFeature: "saml",
	},
	{
		title: "Diagnostics",
		href: "/diagnostics",
		icon: Stethoscope,
		minRole: "admin",
	},
	{ title: "Settings", href: "/settings", icon: Settings, minRole: "super_admin" },
];

export const allNavItems = [
	{ group: "Registry", items: registryNav },
	{ group: "Review", items: reviewNav },
	{ group: "Traces", items: userNav },
	{ group: "Admin", items: adminNav },
];
