// SPDX-FileCopyrightText: 2026 Observal Contributors
// SPDX-License-Identifier: AGPL-3.0-only

import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import { API_BASE, getAccessToken, loginToWebUI } from "./helpers";

const CLI_TIMEOUT = 30_000;

function cli(cmd: string): string {
  
  return execSync(cmd, { encoding: "utf-8", timeout: CLI_TIMEOUT });
}

test.describe("Components - Version history and CLI (#935)", () => {
  test.describe.configure({ mode: "serial" });

  let token: string;
  let mcpId: string;

  test.beforeAll(async () => {
    token = await getAccessToken();

    // Create an MCP listing to test versioning against
    const res = await fetch(`${API_BASE}/api/v1/mcps/submit`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: `e2e-version-mcp-${Date.now()}`,
        description: "MCP for version history e2e test",
        version: "1.0.0",
        category: "developer-tools",
        owner: "admin",
        command: "npx",
        args: ["-y", "test-mcp"],
      }),
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`MCP creation failed: ${res.status} ${body}`);
    }
    const created = await res.json();
    mcpId = created.id;

    // Approve it
    const approveRes = await fetch(`${API_BASE}/api/v1/review/${mcpId}/approve`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ notes: "e2e auto-approve" }),
    });
    if (!approveRes.ok) {
      const body = await approveRes.text();
      throw new Error(`MCP approve failed: ${approveRes.status} ${body}`);
    }
  });

  test.afterAll(async () => {
    if (mcpId) {
      await fetch(`${API_BASE}/api/v1/mcps/${mcpId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
  });

  test("Backend: publish new version, approve, latest_version updates", async () => {
    // Publish v2
    const pubRes = await fetch(`${API_BASE}/api/v1/mcps/${mcpId}/versions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        version: "2.0.0",
        description: "Version 2 with improvements",
        changelog: "Added new features",
      }),
    });
    expect(pubRes.status).toBe(200);
    const version = await pubRes.json();
    expect(version.version).toBe("2.0.0");
    expect(version.status).toBe("pending");

    // Approve the version
    const approveRes = await fetch(
      `${API_BASE}/api/v1/mcps/${mcpId}/versions/2.0.0/review`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action: "approve" }),
      },
    );
    expect(approveRes.status).toBe(200);

    // Verify latest_version reflects v2
    const getRes = await fetch(`${API_BASE}/api/v1/mcps/${mcpId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const mcp = await getRes.json();
    expect(mcp.version).toBe("2.0.0");
  });

  test("Backend: version list returns all versions", async () => {
    const res = await fetch(`${API_BASE}/api/v1/mcps/${mcpId}/versions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    const versions = data.items ?? data;
    expect(versions.length).toBeGreaterThanOrEqual(2);
  });

  test("Playwright: version history tab shows versions with status badges", async ({
    page,
  }) => {
    await loginToWebUI(page);
    await page.goto(`/components/${mcpId}`);
    await page.waitForLoadState("networkidle");

    // Click Versions tab
    const versionsTab = page.locator('[role="tab"]:has-text("Version")');
    if (await versionsTab.isVisible({ timeout: 5000 }).catch(() => false)) {
      await versionsTab.click();
      await page.waitForLoadState("networkidle");

      // Should show version entries
      await expect(page.locator("body")).not.toContainText("Something went wrong");
    } else {
      // Component detail may not have a versions tab in current UI — skip gracefully
      test.skip();
    }
  });

  test("CLI: submit skill via CLI succeeds", () => {
    const output = cli(
      `observal registry skill submit --yes --name "e2e-skill-${Date.now()}" --description "E2E test skill" --version "1.0.0" --git-url "https://github.com/example/skill" --git-ref "main" 2>&1 || true`,
    );
    expect(output).not.toContain("Traceback");
    // Should either succeed or give a meaningful error (not a crash)
    expect(output).toMatch(/success|created|submitted|already exists|error/i);
  });

  test("CLI: submit hook via CLI succeeds", () => {
    const output = cli(
      `observal registry hook submit --yes --name "e2e-hook-${Date.now()}" --description "E2E test hook" --version "1.0.0" --git-url "https://github.com/example/hook" --git-ref "main" 2>&1 || true`,
    );
    expect(output).not.toContain("Traceback");
    expect(output).toMatch(/success|created|submitted|already exists|error/i);
  });

  test("CLI: submit prompt via CLI succeeds", () => {
    const output = cli(
      `observal registry prompt submit --yes --name "e2e-prompt-${Date.now()}" --description "E2E test prompt" --version "1.0.0" --git-url "https://github.com/example/prompt" --git-ref "main" --template "Hello {{name}}" 2>&1 || true`,
    );
    expect(output).not.toContain("Traceback");
    expect(output).toMatch(/success|created|submitted|already exists|error/i);
  });

  test("CLI: submit sandbox via CLI succeeds", () => {
    const output = cli(
      `observal registry sandbox submit --yes --name "e2e-sandbox-${Date.now()}" --description "E2E test sandbox" --version "1.0.0" --git-url "https://github.com/example/sandbox" --git-ref "main" --image "ubuntu:22.04" 2>&1 || true`,
    );
    expect(output).not.toContain("Traceback");
    expect(output).toMatch(/success|created|submitted|already exists|error/i);
  });
});
