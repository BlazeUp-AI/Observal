// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { get, post, put, del } from "@/shared/api-client";

type AuthResponse = {
	user: {
		id: string;
		email: string;
		username?: string | null;
		name: string;
		role: string;
		avatar_url?: string | null;
		created_at: string;
	};
	access_token: string;
	refresh_token: string;
	expires_in: number;
};

export const auth = {
	init: (body: { email: string; name: string; password?: string }) =>
		post<AuthResponse>("/auth/init", body),
	login: (body: { email: string; password: string }) =>
		post<AuthResponse & { must_change_password?: boolean }>(
			"/auth/login",
			body,
		),
	whoami: () =>
		get<{
			id: string;
			email: string;
			username?: string | null;
			name: string;
			role: string;
			avatar_url?: string | null;
		}>("/auth/whoami"),
	exchangeCode: (body: { code: string }) =>
		post<AuthResponse>("/auth/exchange", body),
	deviceConfirm: (userCode: string) =>
		post<{ message: string }>("/auth/device/confirm", { user_code: userCode }),
	changePassword: (body: { current_password: string; new_password: string }) =>
		put<{ message: string }>("/auth/profile/password", body),
	uploadAvatar: (body: { avatar_url: string }) =>
		put<{ avatar_url: string | null }>("/auth/profile/avatar", body),
	deleteAvatar: () => del<{ avatar_url: null }>("/auth/profile/avatar"),
};
