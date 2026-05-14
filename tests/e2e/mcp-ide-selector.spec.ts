// SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { test, expect } from "@playwright/test";
import { loginToWebUI, API_BASE, getAccessToken } from "./helpers";

test.describe("MCP - IDE selector changes command", () => {
  let agentName: string;

  test.beforeAll(async () => {
    const token = await getAccessToken();
    const res = await fetch(`${API_BASE}/api/v1/agents`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const agents = await res.json();
    if (Array.isArray(agents) && agents.length > 0) {
      agentName = agents[0].name;
    } else {
      // Create and approve one for fresh instances
      agentName = `e2e-ide-${Date.now()}`;
      await fetch(`${API_BASE}/api/v1/agents`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: agentName,
          description: "Agent for IDE selector e2e test",
          version: "1.0.0",
          owner: "admin",
          model_name: "claude-sonnet-4-20250514",
          goal_template: {
            description: "E2E test agent",
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

  test("switching IDE dropdown updates pull command", async ({ page }) => {
    await loginToWebUI(page);
    await page.goto(`/agents/${agentName}`);
    await page.waitForLoadState("networkidle");

    // Open the Install tab
    const installTab = page.locator('[role="tab"]:has-text("Install")');
    await installTab.click();
    await page.waitForTimeout(300);

    const commandEl = page.locator('[role="tabpanel"] code').first();

    // Default should be cursor
    await expect(commandEl).toContainText("--ide cursor");

    // Switch to vscode
    const selectTrigger = page
      .locator('[role="tabpanel"] button[role="combobox"]')
      .first();
    await selectTrigger.click();
    await page.locator('[role="option"]:has-text("VS Code")').click();
    await expect(commandEl).toContainText("--ide vscode");

    // Switch to claude-code
    await selectTrigger.click();
    await page.locator('[role="option"]:has-text("Claude Code")').click();
    await expect(commandEl).toContainText("--ide claude-code");

    // Switch to kiro
    await selectTrigger.click();
    await page.locator('[role="option"]:has-text("Kiro")').click();
    await expect(commandEl).toContainText("--ide kiro");
  });
});
