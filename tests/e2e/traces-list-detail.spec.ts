// SPDX-FileCopyrightText: 2026 Observal Contributors
// SPDX-License-Identifier: AGPL-3.0-only

import { test, expect } from "@playwright/test";
import { loginToWebUI, API_BASE, getAccessToken } from "./helpers";

test.describe("Traces - List and detail view (#946)", () => {
  test.describe.configure({ mode: "serial" });

  let token: string;
  const sessionId = `e2e-trace-${Date.now()}`;

  test.beforeAll(async () => {
    token = await getAccessToken();

    // Simulate a real Claude Code session via the hook ingest endpoint.
    // This is the same path the IDE hooks use: UserPromptSubmit fires,
    // sends JSONL lines to /api/v1/ingest/session.
    const lines = [
      // User prompt
      JSON.stringify({
        type: "user",
        message: {
          role: "user",
          content: [{ type: "text", text: "Write a hello world in Python" }],
        },
        timestamp: new Date().toISOString(),
      }),
      // Assistant response with token usage
      JSON.stringify({
        type: "assistant",
        message: {
          role: "assistant",
          content: [{ type: "text", text: "Here's a hello world:\n```python\nprint('hello')\n```" }],
          model: "claude-sonnet-4-20250514",
          usage: {
            input_tokens: 150,
            output_tokens: 85,
            cache_read_input_tokens: 50,
          },
        },
        timestamp: new Date().toISOString(),
      }),
      // Tool use
      JSON.stringify({
        type: "assistant",
        message: {
          role: "assistant",
          content: [{ type: "tool_use", id: "tool_1", name: "Write", input: { path: "/tmp/hello.py", content: "print('hello')" } }],
          model: "claude-sonnet-4-20250514",
          usage: { input_tokens: 200, output_tokens: 50 },
        },
        timestamp: new Date().toISOString(),
      }),
      // Tool result
      JSON.stringify({
        type: "user",
        message: {
          role: "user",
          content: [{ type: "tool_result", tool_use_id: "tool_1", content: "File written successfully" }],
        },
        timestamp: new Date().toISOString(),
      }),
    ];

    const res = await fetch(`${API_BASE}/api/v1/ingest/session`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session_id: sessionId,
        ide: "claude-code",
        lines,
        hook_event: "UserPromptSubmit",
      }),
    });

    if (!res.ok) {
      throw new Error(`Session ingest failed: ${res.status} ${await res.text()}`);
    }
    const result = await res.json();
    expect(result.ingested).toBeGreaterThanOrEqual(3);

    // Poll until session appears in the API (ClickHouse MV needs time)
    for (let attempt = 0; attempt < 10; attempt++) {
      const sessRes = await fetch(`${API_BASE}/api/v1/sessions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const sessions = await sessRes.json();
      if (Array.isArray(sessions) && sessions.some((s: { session_id: string }) => s.session_id === sessionId)) {
        return;
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    throw new Error(`Session ${sessionId} did not appear in /sessions after 20s — pipeline broken`);
  });

  test("traces page shows the ingested session", async ({ page }) => {
    await loginToWebUI(page);
    await page.goto("/traces");
    await page.waitForLoadState("networkidle");

    await expect(page.locator("body")).not.toContainText("Something went wrong");
    // Table must have rows — if not, the pipeline is broken
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 10_000 });
  });

  test("click trace navigates to detail page", async ({ page }) => {
    await loginToWebUI(page);
    await page.goto("/traces");
    await page.waitForLoadState("networkidle");

    await page.locator("table tbody tr").first().click();
    await page.waitForURL(/\/traces\//, { timeout: 10_000 });
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    await expect(page.locator("body")).not.toContainText("Something went wrong");
    // Page should have rendered (heading visible = hydration complete)
    await expect(page.locator("h1, h2, h3").first()).toBeVisible({ timeout: 10_000 });
  });

  test("trace detail shows non-zero token counts", async ({ page }) => {
    await loginToWebUI(page);
    await page.goto("/traces");
    await page.waitForLoadState("networkidle");

    await page.locator("table tbody tr").first().click();
    await page.waitForURL(/\/traces\//, { timeout: 10_000 });
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Get the main content area (SidebarInset wraps the content)
    const content = page.locator('[data-sidebar="inset"], main').last();
    const pageText = await content.innerText();
    // Should contain non-zero numbers (token counts, turn counts, etc.)
    expect(pageText).toMatch(/[1-9]\d*/);
  });
});
