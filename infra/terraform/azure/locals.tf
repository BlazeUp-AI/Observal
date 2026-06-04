# SPDX-FileCopyrightText: 2026 Tanvi Reddy
# SPDX-License-Identifier: AGPL-3.0-only

locals {
  name     = "${var.name_prefix}-${var.environment}"
  is_prod  = var.environment == "prod"
  location = var.location

  clickhouse_self_hosted = var.clickhouse_mode == "self_hosted"

  api_image = "${azurerm_container_registry.main.login_server}/${var.name_prefix}-api:${var.image_tag}"
  web_image = "${azurerm_container_registry.main.login_server}/${var.name_prefix}-web:${var.image_tag}"

  # Connection strings built from managed resources
  database_url   = "postgresql+asyncpg://${azurerm_postgresql_flexible_server.main.administrator_login}:${random_password.db.result}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/observal?sslmode=require"
  redis_url      = "rediss://:${azurerm_redis_cache.main.primary_access_key}@${azurerm_redis_cache.main.hostname}:${azurerm_redis_cache.main.ssl_port}"
  clickhouse_url = local.clickhouse_self_hosted ? "clickhouse://default:${random_password.clickhouse.result}@${azurerm_network_interface.clickhouse[0].private_ip_address}:8123/observal" : var.clickhouse_cloud_url

  tags = {
    Project     = "observal"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
