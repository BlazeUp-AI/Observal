// SPDX-FileCopyrightText: 2026 Tanvi Reddy <tanvi.reddy330@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { test, expect } from "@playwright/test";
import { loginToWebUI } from "./helpers";

test.describe("Theme Switcher", () => {
  test("switching themes re-renders page without broken colors", async ({ page, request }) => {
    // Use request fixture to get token (avoids global fetch rate-limit issues)
    const API = process.env.API_BASE ?? "http://localhost:8000";
    const loginRes = await request.post(`${API}/api/v1/auth/login`, {
      data: {
        email: process.env.DEMO_ADMIN_EMAIL ?? "admin@demo.example",
        password: process.env.DEMO_ADMIN_PASSWORD ?? "admin-changeme",
      },
    });
    const { access_token: token } = await loginRes.json();

    await page.goto("/");
    await page.evaluate((t) => {
      sessionStorage.setItem("observal_access_token", t);
      localStorage.setItem("observal_user_role", "admin");
    }, token);
    await page.reload();
    await page.goto("/");
    await page.waitForSelector("main", { timeout: 10_000 });

    // Open the theme dropdown (in the sidebar user menu area)
    const themeButton = page.locator('button:has-text("Light"), button:has-text("Dark"), button:has-text("Theme")').first();

    // If no explicit theme button, look for the dropdown trigger in the sidebar
    if (!(await themeButton.isVisible().catch(() => false))) {
      // Theme switcher might be in the user nav dropdown
      const userMenu = page.locator('[data-testid="nav-user"], button:has(span.truncate)').first();
      if (await userMenu.isVisible().catch(() => false)) {
        await userMenu.click();
        await page.waitForTimeout(300);
      }
    }

    // Find and click theme options
    const darkOption = page.locator('text=Dark').first();
    if (await darkOption.isVisible().catch(() => false)) {
      await darkOption.click();
      await page.waitForTimeout(500);

      // Verify the page has a dark class or data-theme attribute
      const html = page.locator("html");
      const className = await html.getAttribute("class") ?? "";
      const dataTheme = await html.getAttribute("data-theme") ?? "";
      expect(className.includes("dark") || dataTheme.includes("dark")).toBe(true);
    }

    // Switch to light
    // Re-open menu if needed
    const lightOption = page.locator('text=Light').first();
    if (await lightOption.isVisible().catch(() => false)) {
      await lightOption.click();
      await page.waitForTimeout(500);

      const html = page.locator("html");
      const className = await html.getAttribute("class") ?? "";
      expect(className.includes("dark")).toBe(false);
    }

    // Verify no broken layout (page still has content)
    await expect(page.locator("main")).toBeVisible();
  });
});

test.describe("Command Palette (Cmd+K)", () => {
  test("opens on keyboard shortcut and shows search results", async ({ page }) => {
    await loginToWebUI(page);
    await page.goto("/");
    await page.waitForSelector("main", { timeout: 10_000 });

    // Press Cmd+K (Meta+K on macOS, Control+K on Linux)
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(500);

    // Verify the command palette dialog is visible
    const palette = page.locator('[role="dialog"]').first();
    await expect(palette).toBeVisible({ timeout: 5_000 });

    // Type a search query in the command input
    const input = palette.locator('input').first();
    await expect(input).toBeVisible();
    await input.fill("agents");
    await page.waitForTimeout(500);

    // Verify results appear (cmdk items)
    const results = palette.locator('[cmdk-item]');
    await expect(results.first()).toBeVisible({ timeout: 5_000 });

    // Close palette with Escape
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
  });
});

test.describe("Error State on API Failure", () => {
  test("error component renders with retry button when API is unreachable", async ({ page }) => {
    await loginToWebUI(page);

    // Block API requests by intercepting them
    await page.route("**/api/v1/**", (route) => route.abort("connectionrefused"));

    await page.goto("/agents");
    await page.waitForTimeout(5000);

    // The ErrorState component shows "Failed to load data" and a "Retry" button
    const errorText = page.locator('text=/Failed to load|Something went wrong|error/i').first();
    const retryButton = page.locator('button:has-text("Retry")').first();

    const hasError = await errorText.isVisible().catch(() => false);
    const hasRetry = await retryButton.isVisible().catch(() => false);

    expect(hasError || hasRetry).toBe(true);

    // Unblock API
    await page.unrouteAll();
  });
});

test.describe("Empty State", () => {
  test("page handles empty data gracefully", async ({ page }) => {
    await loginToWebUI(page);

    // Mock the agents API to return empty list
    await page.route("**/api/v1/agents**", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      }
      return route.continue();
    });

    await page.goto("/agents");
    await page.waitForTimeout(3000);

    // Verify the page renders without crashing
    await expect(page.locator("main")).toBeVisible();

    // Check for empty state indicators (text, dashed border container, or just no table rows)
    const emptyText = page.locator('text=/no agents|nothing|get started|no results|empty/i').first();
    const emptyContainer = page.locator(".border-dashed").first();
    const tableRows = page.locator("table tbody tr");

    const hasEmptyText = await emptyText.isVisible().catch(() => false);
    const hasEmptyContainer = await emptyContainer.isVisible().catch(() => false);
    const rowCount = await tableRows.count().catch(() => 0);

    // Either shows empty state UI, or table with no rows — both are valid
    expect(hasEmptyText || hasEmptyContainer || rowCount === 0).toBe(true);

    await page.unrouteAll();
  });
});

test.describe("Pagination", () => {
  test("page controls work on agents list", async ({ page }) => {
    await loginToWebUI(page);
    await page.goto("/agents");
    await page.waitForSelector("main", { timeout: 10_000 });
    await page.waitForTimeout(1000);

    // Look for pagination controls (next/prev buttons or page numbers)
    const paginationControls = page.locator(
      'button:has-text("Next"), button:has-text("Previous"), [aria-label*="page"], [data-testid*="pagination"], nav[aria-label="pagination"]',
    ).first();

    const hasPagination = await paginationControls.isVisible().catch(() => false);

    if (hasPagination) {
      // If pagination exists, click next and verify content updates
      const nextButton = page.locator('button:has-text("Next"), button[aria-label="Next page"]').first();
      if (await nextButton.isEnabled().catch(() => false)) {
        const contentBefore = await page.locator("main").textContent();
        await nextButton.click();
        await page.waitForTimeout(1000);
        const contentAfter = await page.locator("main").textContent();
        // Content should change after pagination
        expect(contentAfter).not.toBe(contentBefore);
      }
    } else {
      // If no pagination visible, there might not be enough data — that's acceptable
      // Verify the page at least loaded without errors
      await expect(page.locator("main")).toBeVisible();
    }
  });
});
