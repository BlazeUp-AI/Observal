// SPDX-License-Identifier: AGPL-3.0-only

"use client";

import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { PageHeader } from "@/components/layouts/page-header";
import { AdoptionTab } from "./components/adoption-tab";
import { CostTab } from "./components/cost-tab";
import { InvestmentsTab } from "./components/investments-tab";
import { InsightsTab } from "./components/insights-tab";
import { DepartmentsTab } from "./components/departments-tab";
import { VelocityTab } from "./components/velocity-tab";

export default function DashboardPage() {
  return (
    <>
      <PageHeader
        title="Executive Dashboard"
        breadcrumbs={[{ label: "Dashboard" }]}
      />
      <div className="p-6 w-full mx-auto space-y-6">
        <Tabs defaultValue="adoption" className="w-full">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="adoption">AI Adoption</TabsTrigger>
            <TabsTrigger value="cost">Cost Intelligence</TabsTrigger>
            <TabsTrigger value="investments">Investments</TabsTrigger>
            <TabsTrigger value="insights">Agent Insights</TabsTrigger>
            <TabsTrigger value="departments">Departments</TabsTrigger>
            <TabsTrigger value="velocity">Velocity</TabsTrigger>
          </TabsList>

          <TabsContent value="adoption">
            <AdoptionTab />
          </TabsContent>

          <TabsContent value="cost">
            <CostTab />
          </TabsContent>

          <TabsContent value="investments">
            <InvestmentsTab />
          </TabsContent>

          <TabsContent value="insights">
            <InsightsTab />
          </TabsContent>

          <TabsContent value="departments">
            <DepartmentsTab />
          </TabsContent>

          <TabsContent value="velocity">
            <VelocityTab />
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
