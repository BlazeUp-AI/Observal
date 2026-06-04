# SPDX-FileCopyrightText: 2026 Tanvi Reddy
# SPDX-License-Identifier: AGPL-3.0-only

resource "azurerm_redis_cache" "main" {
  name                 = "${local.name}-redis"
  location             = azurerm_resource_group.main.location
  resource_group_name  = azurerm_resource_group.main.name
  capacity             = var.redis_capacity
  family               = var.redis_sku == "Premium" ? "P" : "C"
  sku_name             = var.redis_sku
  non_ssl_port_enabled = false
  minimum_tls_version  = "1.2"

  redis_configuration {
    maxmemory_policy = "volatile-lru"
  }

  tags = local.tags
}
