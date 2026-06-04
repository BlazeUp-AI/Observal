# SPDX-FileCopyrightText: 2026 Tanvi Reddy
# SPDX-License-Identifier: AGPL-3.0-only

# Staging environment - cost-optimized for development/testing.

subscription_id = "6a0284fc-791a-4d77-9520-69cdaa79ba44"
environment     = "staging"
location        = "eastus"
name_prefix     = "observal"

# Smaller SKUs for staging
postgresql_sku        = "B_Standard_B2s"
postgresql_storage_gb = 32
redis_sku             = "Standard"
redis_capacity        = 0

# Minimal replicas
api_min_replicas    = 1
api_max_replicas    = 3
web_min_replicas    = 1
web_max_replicas    = 2
worker_min_replicas = 1
worker_max_replicas = 2

# Smaller ClickHouse VM
clickhouse_vm_size      = "Standard_D2s_v5"
clickhouse_disk_size_gb = 50

# Managed Grafana
grafana_enabled = true

# Minimum allowed by Azure is 30
log_retention_days = 30
