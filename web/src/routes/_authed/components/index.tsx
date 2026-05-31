// SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only

import { createFileRoute } from "@tanstack/react-router";
import { lazy } from "react";
const ComponentsPage = lazy(() => import("@/features/registry/pages/components/index"));

export const Route = createFileRoute("/_authed/components/")({
  component: ComponentsPage,
});
