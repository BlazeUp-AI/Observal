data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  name = "${var.name_prefix}-${var.environment}"
  azs  = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  enable_tls = var.domain_name != "" && var.route53_zone_id != ""
  app_url    = local.enable_tls ? "https://${var.domain_name}" : "http://${aws_lb.app.dns_name}"

  clickhouse_self_hosted = var.clickhouse_mode == "self_hosted"

  # Internal DNS names — ECS tasks resolve these via the private Route53 zone.
  clickhouse_host_internal = local.clickhouse_self_hosted ? "clickhouse.${var.internal_dns_zone}" : ""
  grafana_host_internal    = "grafana.${var.internal_dns_zone}"

  # Effective ClickHouse connection (stored in SSM, injected into ECS tasks).
  clickhouse_url = local.clickhouse_self_hosted ? "clickhouse://default@${local.clickhouse_host_internal}:8123/observal" : var.clickhouse_cloud_url

  ssm_prefix = "/${local.name}"
}
