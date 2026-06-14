# SPDX-FileCopyrightText: 2026 BlazeUp AI
# SPDX-License-Identifier: AGPL-3.0-only

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

locals {
  name = "${var.name_prefix}-${var.environment}"
  azs  = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  # BYO-VPC
  should_create_vpc  = var.vpc_id == null
  vpc_id             = local.should_create_vpc ? aws_vpc.main[0].id : var.vpc_id
  vpc_cidr           = data.aws_vpc.vpc.cidr_block
  private_subnet_ids = local.should_create_vpc ? aws_subnet.private[*].id : var.private_subnet_ids
  public_subnet_ids  = local.should_create_vpc ? aws_subnet.public[*].id : var.public_subnet_ids

  enable_tls = var.enable_tls && var.domain_name != "" && var.route53_zone_id != ""
  app_url    = var.domain_name != "" ? "${local.enable_tls ? "https" : "http"}://${var.domain_name}" : "http://${aws_lb.app.dns_name}"

  is_enterprise = var.observal_license_key != ""
  ssm_prefix    = "/${local.name}"

  api_image = "${var.image_repo_api}:${var.image_tag}"
  web_image = "${var.image_repo_web}:${var.image_tag}"

  # ── Sizing presets ──────────────────────────────────────────────────────
  presets = {
    small = {
      ecs_instance_type    = "t3.large"
      api_cpu              = 512
      api_memory           = 1024
      api_desired_count    = 1
      web_cpu              = 256
      web_memory           = 512
      web_desired_count    = 1
      worker_cpu           = 256
      worker_memory        = 512
      worker_desired_count = 1
      data_instance_type   = "t3.medium"
      data_volume_size_gb  = 50
    }
    medium = {
      ecs_instance_type    = "t3.large"
      api_cpu              = 512
      api_memory           = 1024
      api_desired_count    = 1
      web_cpu              = 256
      web_memory           = 512
      web_desired_count    = 1
      worker_cpu           = 512
      worker_memory        = 1024
      worker_desired_count = 1
      data_instance_type   = "t3.medium"
      data_volume_size_gb  = 100
    }
  }

  use_preset = var.sizing != "custom"

  effective_ecs_instance_type    = local.use_preset ? local.presets[var.sizing].ecs_instance_type : var.ecs_instance_type
  effective_api_cpu              = local.use_preset ? local.presets[var.sizing].api_cpu : var.api_cpu
  effective_api_memory           = local.use_preset ? local.presets[var.sizing].api_memory : var.api_memory
  effective_api_desired_count    = local.use_preset ? local.presets[var.sizing].api_desired_count : var.api_desired_count
  effective_web_cpu              = local.use_preset ? local.presets[var.sizing].web_cpu : var.web_cpu
  effective_web_memory           = local.use_preset ? local.presets[var.sizing].web_memory : var.web_memory
  effective_web_desired_count    = local.use_preset ? local.presets[var.sizing].web_desired_count : var.web_desired_count
  effective_worker_cpu           = local.use_preset ? local.presets[var.sizing].worker_cpu : var.worker_cpu
  effective_worker_memory        = local.use_preset ? local.presets[var.sizing].worker_memory : var.worker_memory
  effective_worker_desired_count = local.use_preset ? local.presets[var.sizing].worker_desired_count : var.worker_desired_count
  effective_data_instance_type   = local.use_preset ? local.presets[var.sizing].data_instance_type : var.data_instance_type
  effective_data_volume_size_gb  = local.use_preset ? local.presets[var.sizing].data_volume_size_gb : var.data_volume_size_gb
}

data "aws_vpc" "vpc" {
  id = local.vpc_id
}
