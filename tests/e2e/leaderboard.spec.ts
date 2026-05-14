// SPDX-FileCopyrightText: 2026 Observal Contributors
// SPDX-License-Identifier: AGPL-3.0-only

import { test, expect, Page } from "@playwright/test";
import { API_BASE, getAccessToken } from "./helpers";

/**
 * Login by setting sessionStorage (access token) and localStorage (role).
 * The shared loginToWebUI helper uses localStorage which is outdated —
 * the app now reads the access token from sessionStorage.
 */
async function login(page: Page) {
  const token = await getAccessToken();
  await page.goto("/");
  await page.evaluate((t) => {
    sessionStorage.setItem("observal_access_token", t);
    localStorage.setItem("observal_user_role", "admin");
  }, token);
  await page.reload();
}

/**
 * E2E: Leaderboard — page load and time window selector
 * Issue #962
 */
test.describe("Leaderboard", () => {
  let agentName: string;

  test.beforeAll(async () => {
    const token = await getAccessToken();

    // Ensure at least one approved agent exists so the leaderboard has data
    const res = await fetch(`${API_BASE}/api/v1/agents`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const agents = await res.json();

    if (Array.isArray(agents) && agents.length > 0) {
      agentName = agents[0].name;
    } else {
      agentName = `e2e-leaderboard-${Date.now()}`;
      await fetch(`${API_BASE}/api/v1/agents`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: agentName,
          description: "Agent seeded for leaderboard e2e tests",
          version: "1.0.0",
          owner: "admin",
          model_name: "claude-sonnet-4-20250514",
          goal_template: {
            description: "Leaderboard test agent",
            sections: [{ name: "General", description: "General purpose" }],
          },
        }),
      });
      await fetch(`${API_BASE}/api/v1/review/agents/${agentName}/approve`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  });

  /**
   * P1: Leaderboard loads with ranked agents
   */
  test("leaderboard loads with ranked agents", async ({ page }) => {
    await login(page);
    await page.goto("/leaderboard");
    await page.waitForLoadState("networkidle");

    // Page header renders
    await expect(page.getByRole("heading", { name: "Leaderboard" })).toBeVisible();

    // Time window tabs are present
    await expect(page.locator('button[role="tab"]:has-text("7 days")')).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("30 days")')).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("All time")')).toBeVisible();

    // The Agents tab should be selected by default
    await expect(page.locator('button[role="tab"]:has-text("Agents")')).toHaveAttribute("data-state", "active");

    // Either the ranked table renders (with column headers and rows)
    // or the empty state renders — both are valid loaded states
    const mainContent = page.locator("main");
    const tableHeader = mainContent.locator("text=Downloads").first();
    const emptyState = mainContent.getByText("No rankings yet");

    // Wait for either the table or empty state to appear
    await expect(tableHeader.or(emptyState)).toBeVisible({ timeout: 10_000 });

    // If the table is showing, verify structure
    if (await tableHeader.isVisible()) {
      await expect(mainContent.locator("text=Rating").first()).toBeVisible();
      await expect(mainContent.locator("text=Version").first()).toBeVisible();

      // At least one ranked agent row is visible (link to /agents/...)
      const agentRows = mainContent.locator('a[href^="/agents/"]');
      await expect(agentRows.first()).toBeVisible({ timeout: 10_000 });
      const count = await agentRows.count();
      expect(count).toBeGreaterThanOrEqual(1);
    } else {
      // Empty state is showing — verify it has the expected message
      await expect(mainContent.getByText("Install agents via the CLI or web UI to populate the leaderboard.")).toBeVisible();
    }
  });

  /**
   * P2: Time window selector updates table data
   */
  test("time window selector updates table data", async ({ page }) => {
    await login(page);
    await page.goto("/leaderboard");
    await page.waitForLoadState("networkidle");

    // Default window is 7d — the "7 days" tab should be active (data-state="active")
    const tab7d = page.locator('button[role="tab"]:has-text("7 days")');
    await expect(tab7d).toHaveAttribute("data-state", "active");

    // Switch to 30 days and verify the API is called with window=30d
    const [response30d] = await Promise.all([
      page.waitForResponse((r) =>
        r.url().includes("/overview/leaderboard") && r.url().includes("window=30d"),
      ),
      page.locator('button[role="tab"]:has-text("30 days")').click(),
    ]);
    expect(response30d.status()).toBe(200);

    // The 30 days tab should now be active
    const tab30d = page.locator('button[role="tab"]:has-text("30 days")');
    await expect(tab30d).toHaveAttribute("data-state", "active");

    // Switch to All time and verify the API is called with window=all
    const [responseAll] = await Promise.all([
      page.waitForResponse((r) =>
        r.url().includes("/overview/leaderboard") && r.url().includes("window=all"),
      ),
      page.locator('button[role="tab"]:has-text("All time")').click(),
    ]);
    expect(responseAll.status()).toBe(200);

    // The All time tab should now be active
    const tabAll = page.locator('button[role="tab"]:has-text("All time")');
    await expect(tabAll).toHaveAttribute("data-state", "active");

    // Content area is still present after switching (either table rows or empty state)
    const mainContent = page.locator('main');
    const tableContent = mainContent.locator('a[href^="/agents/"]').first();
    const emptyState = mainContent.getByText("No rankings yet");
    await expect(tableContent.or(emptyState)).toBeVisible({ timeout: 10_000 });
  });
});
