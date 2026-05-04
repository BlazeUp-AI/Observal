# Observal on AWS — Terraform

Production-shaped self-hosted Observal in your own AWS account. One `terraform apply` provisions:

- **VPC** — public + private subnets across 2 AZs, NAT gateway, VPC flow logs
- **Application Load Balancer** — HTTPS via DNS-validated ACM (when domain supplied), path-based routing
- **ECS Fargate cluster** — `api`, `web`, `worker` as separate services with target-tracking CPU autoscaling. `init` runs as a one-shot `RunTask` on every image bump
- **RDS Postgres 16** — Multi-AZ on `prod`, encrypted, automated backups, Performance Insights, Enhanced Monitoring, log exports
- **ElastiCache Redis 7** — 2-node replication group with automatic failover on `prod`, slow-log to CloudWatch
- **Data tier EC2** — single host running ClickHouse + Grafana + Prometheus on EBS gp3, ENI with static private IP, internal Route 53 zone for DNS, daily ClickHouse → S3 snapshot via systemd timer
- **S3 backups bucket** — versioned, AES256, lifecycle to STANDARD_IA → GLACIER_IR → expire, TLS-only access
- **CloudWatch log groups** — per-service for ECS tasks, data host, RDS, Redis, VPC flow logs
- **SSM Parameter Store** — generated DB / ClickHouse / SECRET_KEY / Grafana passwords, plus pre-built connection URLs injected into ECS tasks
- **SSM Session Manager** — shell access to the data host, no SSH

## Architecture

```
                      ┌──────────────────────────┐
                Internet → │   ALB (443)   │
                      └──┬─────┬─────┬──────────┘
              path /api/*│     │/grafana/*
                         ▼     ▼     ▼ default
              ┌──────────────┐  ┌────────────────┐  ┌──────────┐
              │ ECS Fargate  │  │  EC2 data host │  │   ECS    │
              │ api service  │  │  (single AZ)   │  │   web    │
              │  2..10×      │  │  ClickHouse    │  │ 2..6×    │
              └─────┬────────┘  │  Grafana 3001  │  └──────────┘
                    │           │  Prometheus    │
              ┌─────┴────────┐  └────────┬───────┘
              │ ECS Fargate  │           │
              │   worker     │           │
              │   1..5×      │           ▼
              └────┬─────────┘  EBS gp3 100GB at /data
                   │
                   ▼
         ┌──────────────────────────────┐
         │  RDS Postgres 16 (Multi-AZ)  │
         │  ElastiCache Redis (2-node)  │
         └──────────────────────────────┘
```

The stateless app tier (api/web/worker) lives on Fargate across both AZs with autoscaling and rolling deploys. The stateful data tier (ClickHouse + Grafana + Prometheus) lives on a single EC2 with EBS so ClickHouse keeps its disk across instance replacements. Real ClickHouse HA is out of scope — set `clickhouse_mode = "cloud"` and point at ClickHouse Cloud when you need it.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Terraform | ≥ 1.6 | `brew install terraform` |
| AWS CLI | ≥ 2.x | `brew install awscli` |
| Session Manager plugin | latest | [docs](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) |

You also need:

- An AWS account with billing enabled.
- An IAM principal with permission to manage VPC, EC2, RDS, ElastiCache, ECS, IAM, ALB, ACM, Route53, SSM, CloudWatch, S3.
- (Optional) a Route 53 hosted zone if you want HTTPS on a custom domain.
- (Recommended) an S3 bucket + DynamoDB table for remote state (uncomment the `backend "s3"` block in `versions.tf`).

## Quickstart

```bash
cd infra/terraform/aws

# 1. Authenticate (any of these works)
export AWS_PROFILE=observal-prod
# or: aws configure sso

# 2. Configure
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars

# 3. Apply
terraform init
terraform plan -out tf.plan
terraform apply tf.plan
```

A clean apply takes ~12–15 minutes (RDS dominates). When it finishes:

```bash
terraform output app_url
terraform output ecs_cluster_name
terraform output data_host_ssm_session_command
```

A working module-call example lives at [`examples/minimal`](examples/minimal/).

## What credentials and inputs are required?

The module generates all application secrets (Postgres password, ClickHouse password, `SECRET_KEY`, Grafana admin) and stores them in SSM Parameter Store as `SecureString`s. ECS task definitions reference them via the `secrets` block, so they're injected as environment variables at task start — never written to disk.

You only need to supply:

1. **AWS credentials** — `AWS_PROFILE`, `aws configure sso`, or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`.
2. **`region`** (default `us-east-1`).
3. **(Optional) `domain_name` + `route53_zone_id`** for HTTPS on a real domain.
4. **(Optional) `alb_ingress_cidrs`** to lock the ALB to specific IP ranges.
5. **(Optional) `clickhouse_mode = "cloud"` + `clickhouse_cloud_*`** to use ClickHouse Cloud instead of self-hosting.

## Operating the install

**Open a shell on the data host (no SSH key needed):**
```bash
$(terraform output -raw data_host_ssm_session_command)
```

**Tail an ECS service:**
```bash
aws logs tail /aws/ecs/observal-prod/api --follow
```

**Force a rolling deploy of the api (e.g. after pushing a new image with the same tag):**
```bash
aws ecs update-service \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service observal-prod-api \
  --force-new-deployment
```

**Re-run migrations:**
```bash
$(terraform output -raw init_run_task_command)
```

**Read a generated secret:**
```bash
aws ssm get-parameter --with-decryption \
  --name /observal-prod/SECRET_KEY \
  --query Parameter.Value --output text
```

**Upgrade to a new release:** bump `image_tag` in `terraform.tfvars` and re-apply. The `null_resource.run_init` rerun handles migrations; ECS handles the rolling deploy.

## Costs (rough, us-east-1, on-demand)

| Resource | Default | ~$/month |
|----------|---------|----------|
| Fargate api 2× (0.5 vCPU / 1 GB) | always-on | $30 |
| Fargate web 2× (0.25 vCPU / 0.5 GB) | always-on | $15 |
| Fargate worker 1× (0.5 vCPU / 1 GB) | always-on | $15 |
| EC2 t3.large (data host) | 1× | $60 |
| RDS db.t4g.small Multi-AZ | 1 | $50 |
| ElastiCache cache.t4g.micro × 2 | 1 | $25 |
| ALB | 1 | $20 |
| NAT Gateway | 1 | $33 + egress |
| EBS gp3 100 GB | 1 | $8 |
| S3 backups (1 GB cold) | — | $0.10 |
| **Total baseline** | | **~$255/month** |

Drop to single-AZ RDS, single Redis node, and `worker_desired_count = 0` for staging by setting `environment != "prod"`.

## Production hardening checklist

Before using in front of customers:

- [ ] Switch the Terraform backend to S3 + DynamoDB (uncomment the block in `versions.tf`)
- [ ] Restrict `alb_ingress_cidrs` to known CIDRs
- [ ] Enable AWS Config + GuardDuty in the account
- [ ] Wire CloudWatch alarms on RDS CPU / freeable memory, ECS service CPU, ALB 5xx
- [ ] Add a WAF in front of the ALB (`aws_wafv2_web_acl_association`)
- [ ] Set `transit_encryption_enabled = true` on the ElastiCache replication group and switch `REDIS_URL` to `rediss://...`
- [ ] Replace the GitHub-tarball pull in `user-data.sh.tftpl` with your own signed artifact location
- [ ] Move ClickHouse to ClickHouse Cloud (`clickhouse_mode = "cloud"`) for actual HA

## Layout

```
versions.tf                # provider versions + (commented) S3 backend
variables.tf               # all inputs
locals.tf                  # AZ lookup, derived names, internal DNS
vpc.tf                     # VPC, subnets, NAT, route tables, flow logs, private zone
security.tf                # security groups (alb, ecs_tasks, data_host, db, redis)
iam.tf                     # ECS execution + task roles, EC2 data-host role
secrets.tf                 # random_password + SSM Parameter Store (raw + URLs)
postgresql.tf              # RDS Postgres + Enhanced Monitoring role
redis.tf                   # ElastiCache replication group
clickhouse.tf              # data-tier EC2 (CH + Grafana + Prometheus), private DNS
ecs.tf                     # Fargate cluster, task defs, services, autoscaling, init
alb.tf                     # ALB, target groups, listeners, listener rules, ACM
s3.tf                      # backups bucket with lifecycle and TLS-only policy
logs.tf                    # CloudWatch log groups
dns.tf                     # public Route 53 record (alias to ALB)
outputs.tf                 # app_url, ecs cluster/services, log groups, ...
user-data.sh.tftpl         # cloud-init for the data host (CH + Grafana + Prometheus)
terraform.tfvars.example
examples/minimal/          # ready-to-apply module-call example
```
