# SPDX-FileCopyrightText: 2026 Tanvi Reddy
# SPDX-License-Identifier: AGPL-3.0-only

resource "azurerm_resource_group" "main" {
  name     = "${local.name}-rg"
  location = local.location
  tags     = local.tags
}
