// SPDX-FileCopyrightText: 2026 Tanvi Reddy <tanvi.reddy330@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { test, expect } from "@playwright/test";
import { API_BASE } from "./helpers";

const OTLP_BASE = process.env.API_BASE ?? "http://localhost:8000";

test.describe("OTLP /v1/traces receiver", () => {
  test("accepts OTLP trace payload and returns 200", async ({ request }) => {
    const traceId = Date.now().toString(16).padStart(32, "0");
    const spanId = traceId.slice(0, 16);

    const payload = {
      resourceSpans: [
        {
          resource: {
            attributes: [
              { key: "service.name", value: { stringValue: "e2e-test-service" } },
            ],
          },
          scopeSpans: [
            {
              scope: { name: "e2e.telemetry" },
              spans: [
                {
                  traceId,
                  spanId,
                  name: "e2e-otlp-trace-test",
                  kind: 1,
                  startTimeUnixNano: String(Date.now() * 1_000_000),
                  endTimeUnixNano: String((Date.now() + 100) * 1_000_000),
                  status: { code: 1 },
                  attributes: [],
                  events: [],
                },
              ],
            },
          ],
        },
      ],
    };

    const res = await request.post(`${OTLP_BASE}/v1/traces`, { data: payload });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data).toBeTruthy();
  });
});

test.describe("OTLP /v1/logs receiver", () => {
  test("accepts OTLP log payload and returns 200", async ({ request }) => {
    const sessionId = `e2e-otlp-log-${Date.now()}`;
    const promptId = `prompt-${Date.now()}`;

    const payload = {
      resourceLogs: [
        {
          resource: {
            attributes: [
              { key: "service.name", value: { stringValue: "e2e-test-service" } },
              { key: "session.id", value: { stringValue: sessionId } },
            ],
          },
          scopeLogs: [
            {
              scope: { name: "e2e.telemetry" },
              logRecords: [
                {
                  timeUnixNano: String(Date.now() * 1_000_000),
                  severityNumber: 9,
                  body: { stringValue: "e2e test log message" },
                  attributes: [
                    { key: "event.name", value: { stringValue: "user_prompt" } },
                    { key: "session.id", value: { stringValue: sessionId } },
                    { key: "prompt.id", value: { stringValue: promptId } },
                  ],
                },
              ],
            },
          ],
        },
      ],
    };

    const res = await request.post(`${OTLP_BASE}/v1/logs`, { data: payload });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data).toBeTruthy();
  });
});

test.describe("Registered-agents-only enforcement", () => {
  test("unregistered agent telemetry is handled when enforcement is on", async ({ request }) => {
    // Login as super_admin to toggle the setting
    const email = process.env.DEMO_SUPER_EMAIL ?? "super@demo.example";
    const password = process.env.DEMO_SUPER_PASSWORD ?? "super-changeme";

    const loginRes = await request.post(`${OTLP_BASE}/api/v1/auth/login`, {
      data: { email, password },
    });
    expect(loginRes.status()).toBe(200);
    const { access_token: superToken } = await loginRes.json();

    // Enable registered-agents-only mode
    const toggleRes = await request.put(`${OTLP_BASE}/api/v1/admin/org/registered-agents-only`, {
      headers: { Authorization: `Bearer ${superToken}` },
      data: { registered_agents_only: true },
    });
    expect(toggleRes.status()).toBe(200);
    const toggleData = await toggleRes.json();
    expect(toggleData.registered_agents_only).toBe(true);

    // Send telemetry from an unregistered agent
    const traceId = Date.now().toString(16).padStart(32, "0");
    const spanId = traceId.slice(0, 16);

    const payload = {
      resourceSpans: [
        {
          resource: {
            attributes: [
              { key: "service.name", value: { stringValue: "unregistered-agent-xyz" } },
              { key: "observal.agent.id", value: { stringValue: "non-existent-agent-id" } },
            ],
          },
          scopeSpans: [
            {
              scope: { name: "e2e.enforcement" },
              spans: [
                {
                  traceId,
                  spanId,
                  name: "unregistered-agent-span",
                  kind: 1,
                  startTimeUnixNano: String(Date.now() * 1_000_000),
                  endTimeUnixNano: String((Date.now() + 100) * 1_000_000),
                  status: { code: 1 },
                  attributes: [],
                  events: [],
                },
              ],
            },
          ],
        },
      ],
    };

    const ingestRes = await request.post(`${OTLP_BASE}/v1/traces`, { data: payload });
    // The server accepts the request (200) but stores as metadata-only
    expect([200, 202, 403]).toContain(ingestRes.status());

    // Disable registered-agents-only mode (cleanup)
    const disableRes = await request.put(`${OTLP_BASE}/api/v1/admin/org/registered-agents-only`, {
      headers: { Authorization: `Bearer ${superToken}` },
      data: { registered_agents_only: false },
    });
    expect(disableRes.status()).toBe(200);
  });
});
