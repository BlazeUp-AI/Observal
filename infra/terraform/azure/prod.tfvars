# SPDX-FileCopyrightText: 2026 Tanvi Reddy
# SPDX-License-Identifier: AGPL-3.0-only

# Production environment - HA, zone-redundant, deletion-protected.

subscription_id = "6a0284fc-791a-4d77-9520-69cdaa79ba44"
environment     = "prod"
location        = "eastus"
name_prefix     = "observal"

# Production-grade PostgreSQL
postgresql_sku        = "GP_Standard_D2ds_v5"
postgresql_storage_gb = 128
redis_sku             = "Standard"
redis_capacity        = 1

# Production replicas with autoscaling
api_min_replicas    = 2
api_max_replicas    = 10
web_min_replicas    = 2
web_max_replicas    = 6
worker_min_replicas = 1
worker_max_replicas = 5

# Larger ClickHouse VM for production workloads
clickhouse_vm_size      = "Standard_D4s_v5"
clickhouse_disk_size_gb = 200

# Managed Grafana
grafana_enabled = true

# 30-day log retention
log_retention_days = 30
