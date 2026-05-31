// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Shared HTTP client + auth state management for all API domain modules.
 * Handles auth headers, token refresh, retries, error parsing, and session storage.
 */

// ── Auth State ──────────────────────────────────────────────────────

const STORAGE_KEY_ACCESS_TOKEN = "observal_access_token";
const STORAGE_KEY_REFRESH_TOKEN = "observal_refresh_token";
const STORAGE_KEY_USER_ROLE = "observal_user_role";
const STORAGE_KEY_USER_NAME = "observal_user_name";
const STORAGE_KEY_USER_EMAIL = "observal_user_email";
const STORAGE_KEY_USER_USERNAME = "observal_user_username";
const STORAGE_KEY_USER_AVATAR = "observal_user_avatar";

export function getAccessToken(): string | null {
	if (typeof window === "undefined") return null;
	return sessionStorage.getItem(STORAGE_KEY_ACCESS_TOKEN);
}

export function getRefreshToken(): string | null {
	if (typeof window === "undefined") return null;
	return localStorage.getItem(STORAGE_KEY_REFRESH_TOKEN);
}

export function setTokens(accessToken: string, refreshToken: string) {
	sessionStorage.setItem(STORAGE_KEY_ACCESS_TOKEN, accessToken);
	localStorage.setItem(STORAGE_KEY_REFRESH_TOKEN, refreshToken);
}

export function clearSession() {
	sessionStorage.removeItem(STORAGE_KEY_ACCESS_TOKEN);
	localStorage.removeItem(STORAGE_KEY_REFRESH_TOKEN);
	localStorage.removeItem("observal_api_key");
	localStorage.removeItem(STORAGE_KEY_USER_ROLE);
	localStorage.removeItem(STORAGE_KEY_USER_NAME);
	localStorage.removeItem(STORAGE_KEY_USER_EMAIL);
	localStorage.removeItem(STORAGE_KEY_USER_USERNAME);
	localStorage.removeItem(STORAGE_KEY_USER_AVATAR);
}

export function setUserRole(role: string) {
	localStorage.setItem(STORAGE_KEY_USER_ROLE, role);
}

export function getUserRole(): string | null {
	if (typeof window === "undefined") return null;
	return localStorage.getItem(STORAGE_KEY_USER_ROLE);
}

export function setUserName(name: string) {
	localStorage.setItem(STORAGE_KEY_USER_NAME, name);
}

export function getUserName(): string | null {
	if (typeof window === "undefined") return null;
	return localStorage.getItem(STORAGE_KEY_USER_NAME);
}

export function setUserEmail(email: string) {
	localStorage.setItem(STORAGE_KEY_USER_EMAIL, email);
}

export function getUserEmail(): string | null {
	if (typeof window === "undefined") return null;
	return localStorage.getItem(STORAGE_KEY_USER_EMAIL);
}

export function setUserUsername(username: string) {
	localStorage.setItem(STORAGE_KEY_USER_USERNAME, username);
}

export function getUserUsername(): string | null {
	if (typeof window === "undefined") return null;
	return localStorage.getItem(STORAGE_KEY_USER_USERNAME);
}

export function setUserAvatar(avatar: string | null) {
	if (avatar) {
		localStorage.setItem(STORAGE_KEY_USER_AVATAR, avatar);
	} else {
		localStorage.removeItem(STORAGE_KEY_USER_AVATAR);
	}
	window.dispatchEvent(new Event("storage"));
}

export function getUserAvatar(): string | null {
	if (typeof window === "undefined") return null;
	return localStorage.getItem(STORAGE_KEY_USER_AVATAR);
}

// ── HTTP Client ─────────────────────────────────────────────────────

const API = "/api/v1";

let _refreshPromise: Promise<boolean> | null = null;

async function _tryRefreshToken(): Promise<boolean> {
	const refreshToken = getRefreshToken();
	if (!refreshToken) return false;

	try {
		const res = await fetch(`${API}/auth/token/refresh`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ refresh_token: refreshToken }),
		});

		if (!res.ok) return false;

		const data = await res.json();
		setTokens(data.access_token, data.refresh_token);
		return true;
	} catch {
		return false;
	}
}

/**
 * Public wrapper for silent token refresh (e.g. new tab with no sessionStorage).
 * Returns true if the access token was restored successfully.
 */
export async function refreshAccessToken(): Promise<boolean> {
	return _tryRefreshToken();
}

async function request<T = unknown>(
	method: string,
	path: string,
	body?: unknown,
): Promise<T> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
	};
	const token = getAccessToken();
	if (token) headers["Authorization"] = `Bearer ${token}`;

	let res: Response | undefined;
	for (let attempt = 0; attempt < 2; attempt++) {
		res = await fetch(`${API}${path}`, {
			method,
			headers,
			body: body !== undefined ? JSON.stringify(body) : undefined,
			cache: "no-store",
		});
		if (res.status < 500) break;
		// Brief pause before retry on 5xx
		if (attempt === 0) await new Promise((r) => setTimeout(r, 500));
	}
	const response = res!;

	if (!response.ok) {
		// Auto-refresh on 401 (except for auth endpoints where 401 means bad credentials)
		if (response.status === 401 && !path.startsWith("/auth/")) {
			// Deduplicate concurrent refresh attempts
			if (!_refreshPromise) {
				_refreshPromise = _tryRefreshToken().finally(() => {
					_refreshPromise = null;
				});
			}
			const refreshed = await _refreshPromise;

			if (refreshed) {
				// Retry the original request with new token
				const newToken = getAccessToken();
				if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
				const retryRes = await fetch(`${API}${path}`, {
					method,
					headers,
					body: body !== undefined ? JSON.stringify(body) : undefined,
					cache: "no-store",
				});
				if (retryRes.ok) {
					if (retryRes.status === 204) return undefined as T;
					return retryRes.json() as Promise<T>;
				}
				const retryText = await retryRes.text().catch(() => "Request failed");
				const retryErr = new Error(retryText);
				(retryErr as Error & { status: number }).status = retryRes.status;
				throw retryErr;
			}

			// Refresh itself failed: session is truly expired
			clearSession();
			if (typeof window !== "undefined") {
				window.location.href = "/login?reason=session_expired";
			}
			throw new Error("Session expired");
		}

		const text = await response.text().catch(() => response.statusText);
		let detail = text;
		try {
			const parsed = JSON.parse(text);
			if (parsed.detail) {
				if (typeof parsed.detail === "string") {
					detail = parsed.detail;
				} else if (Array.isArray(parsed.detail)) {
					detail = parsed.detail
						.map(
							(e: { msg?: string }) =>
								e.msg?.replace(/^Value error, /i, "") || "Validation error",
						)
						.join(". ");
				} else {
					detail = JSON.stringify(parsed.detail);
				}
			} else if (parsed.error) {
				detail =
					typeof parsed.error === "string"
						? parsed.error
						: JSON.stringify(parsed.error);
			}
		} catch {
			// not JSON, use raw text unless it's HTML or a 5xx error
			if (response.status >= 500 || text.trim().startsWith("<")) {
				detail = "Unable to reach the server. Please try again later.";
			}
		}
		const err = new Error(detail);
		(err as Error & { status: number }).status = response.status;
		throw err;
	}

	if (response.status === 204) return undefined as T;

	return response.json() as Promise<T>;
}

export function get<T = unknown>(path: string) {
	return request<T>("GET", path);
}
export function post<T = unknown>(path: string, body?: unknown) {
	return request<T>("POST", path, body);
}
export function put<T = unknown>(path: string, body?: unknown) {
	return request<T>("PUT", path, body);
}
export function del<T = unknown>(path: string) {
	return request<T>("DELETE", path);
}
export function patch<T = unknown>(path: string, body?: unknown) {
	return request<T>("PATCH", path, body);
}

export async function graphql<T = unknown>(
	query: string,
	variables?: Record<string, unknown>,
): Promise<T> {
	const res = await post<{ data: T; errors?: { message: string }[] }>(
		"/graphql",
		{ query, variables },
	);
	if (res.errors?.length) throw new Error(res.errors[0].message);
	return res.data;
}

