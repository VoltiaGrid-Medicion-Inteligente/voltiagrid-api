# Security Groups per component (T-21.2). Least privilege: each group only accepts traffic from
# the group that needs it, and only on its port. Rules are separate resources so groups can
# reference each other without cycles.
#
#   internet --80--> alb --8001,8002,8003,8005--> app (Fargate) --5432--> rds
#   admin (EC2, no inbound) --443--> endpoints (SSM) and S3 (gateway endpoint)
#   admin --5432--> rds (port forwarding)
#
# Terraform removes the default "allow all" egress rule of every group it creates, so a group
# without egress rules cannot start connections.

locals {
  any_ipv4 = "0.0.0.0/0"
}

resource "aws_security_group" "alb" {
  name        = "${var.name}-alb"
  description = "Load balancer: HTTP from the internet"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name}-alb" })
}

resource "aws_security_group" "app" {
  name        = "${var.name}-app"
  description = "Fargate tasks: API ports only from the load balancer"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name}-app" })
}

resource "aws_security_group" "rds" {
  name        = "${var.name}-rds"
  description = "PostgreSQL: 5432 only from the tasks and the admin instance"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name}-rds" })
}

resource "aws_security_group" "admin" {
  name        = "${var.name}-admin"
  description = "Admin instance: no inbound at all, access only through SSM"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name}-admin" })
}

resource "aws_security_group" "endpoints" {
  name        = "${var.name}-endpoints"
  description = "SSM interface endpoints: HTTPS from the admin instance"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name}-endpoints" })
}

# ---------- alb ----------

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from the internet (no domain, so no TLS certificate in the pilot)"
  cidr_ipv4         = local.any_ipv4
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80

  tags = var.tags
}

resource "aws_vpc_security_group_egress_rule" "alb_to_app" {
  for_each = toset([for p in var.app_ports : tostring(p)])

  security_group_id            = aws_security_group.alb.id
  description                  = "Forward to the API tasks"
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = tonumber(each.value)
  to_port                      = tonumber(each.value)

  tags = var.tags
}

# ---------- app (Fargate tasks) ----------

resource "aws_vpc_security_group_ingress_rule" "app_from_alb" {
  for_each = toset([for p in var.app_ports : tostring(p)])

  security_group_id            = aws_security_group.app.id
  description                  = "API port from the load balancer only"
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = tonumber(each.value)
  to_port                      = tonumber(each.value)

  tags = var.tags
}

resource "aws_vpc_security_group_egress_rule" "app_https" {
  security_group_id = aws_security_group.app.id
  description       = "HTTPS to AWS APIs (ECR, Secrets Manager, CloudWatch Logs, S3)"
  cidr_ipv4         = local.any_ipv4
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443

  tags = var.tags
}

resource "aws_vpc_security_group_egress_rule" "app_http_alb" {
  security_group_id = aws_security_group.app.id
  description       = "HTTP to the public load balancer (control center calls F5 through it)"
  cidr_ipv4         = local.any_ipv4
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80

  tags = var.tags
}

resource "aws_vpc_security_group_egress_rule" "app_to_rds" {
  security_group_id            = aws_security_group.app.id
  description                  = "PostgreSQL"
  referenced_security_group_id = aws_security_group.rds.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432

  tags = var.tags
}

# ---------- rds ----------

resource "aws_vpc_security_group_ingress_rule" "rds_from_app" {
  security_group_id            = aws_security_group.rds.id
  description                  = "PostgreSQL from the tasks"
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432

  tags = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_admin" {
  security_group_id            = aws_security_group.rds.id
  description                  = "PostgreSQL from the admin instance (SSM port forwarding)"
  referenced_security_group_id = aws_security_group.admin.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432

  tags = var.tags
}

# ---------- admin instance ----------

resource "aws_vpc_security_group_egress_rule" "admin_to_endpoints" {
  security_group_id            = aws_security_group.admin.id
  description                  = "HTTPS to the SSM endpoints"
  referenced_security_group_id = aws_security_group.endpoints.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443

  tags = var.tags
}

resource "aws_vpc_security_group_egress_rule" "admin_to_s3" {
  security_group_id = aws_security_group.admin.id
  description       = "HTTPS to S3 through the gateway endpoint (T-21.3)"
  prefix_list_id    = var.s3_prefix_list_id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443

  tags = var.tags
}

resource "aws_vpc_security_group_egress_rule" "admin_to_rds" {
  security_group_id            = aws_security_group.admin.id
  description                  = "PostgreSQL (port forwarding to RDS)"
  referenced_security_group_id = aws_security_group.rds.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432

  tags = var.tags
}

# ---------- endpoints ----------

resource "aws_vpc_security_group_ingress_rule" "endpoints_from_admin" {
  security_group_id            = aws_security_group.endpoints.id
  description                  = "HTTPS from the admin instance"
  referenced_security_group_id = aws_security_group.admin.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443

  tags = var.tags
}
