# SPDX-FileCopyrightText: 2026 Tanvi Reddy
# SPDX-License-Identifier: AGPL-3.0-only

# Azure Managed Grafana - enterprise-ready observability dashboard.
# Connects to ClickHouse on the data VM for telemetry queries.

resource "azurerm_dashboard_grafana" "main" {
  count               = var.grafana_enabled ? 1 : 0
  name                = "${var.name_prefix}-${var.environment}-gf"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Standard"

  grafana_major_version = "11"

  identity {
    type = "SystemAssigned"
  }

  azure_monitor_workspace_integrations {
    resource_id = azurerm_log_analytics_workspace.main.id
  }

  tags = local.tags
}

# Grant the current user Grafana Admin role
resource "azurerm_role_assignment" "grafana_admin" {
  count                = var.grafana_enabled ? 1 : 0
  scope                = azurerm_dashboard_grafana.main[0].id
  role_definition_name = "Grafana Admin"
  principal_id         = data.azurerm_client_config.current.object_id
}
