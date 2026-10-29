# Operational database of US-25 (T-25.1): PostgreSQL 16 on RDS, private, encrypted, with automatic
# backups. The master password is created and kept by RDS in Secrets Manager
# (manage_master_user_password): it never appears in the code, the plan or the Terraform state.

resource "aws_db_subnet_group" "this" {
  name        = "${var.name}-db"
  description = "Private subnets of the VPC: the database is never reachable from the internet"
  subnet_ids  = var.private_subnet_ids

  tags = merge(var.tags, { Name = "${var.name}-db" })
}

# Connections without SSL are refused by the server itself.
resource "aws_db_parameter_group" "this" {
  name        = "${var.name}-postgres16"
  family      = "postgres16"
  description = "VoltiaGrid: SSL required"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  # Log every statement slower than 1 second (CloudWatch metrics, US-63).
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  tags = var.tags
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name}-db"
  engine         = "postgres"
  engine_version = "16" # major version; RDS keeps the minor version patched
  instance_class = var.instance_class

  db_name                     = var.db_name
  username                    = var.username
  manage_master_user_password = true

  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  multi_az               = false # pilot: Single-AZ on purpose (docs: Costs)
  parameter_group_name   = aws_db_parameter_group.this.name
  ca_cert_identifier     = "rds-ca-rsa2048-g1"

  # Automatic daily backups kept 7 days, with point-in-time restore. Times in UTC (01:00-02:00 in Colombia).
  backup_retention_period = 7
  backup_window           = "06:00-07:00"
  maintenance_window      = "sun:07:30-sun:08:30"
  copy_tags_to_snapshot   = true

  auto_minor_version_upgrade = true
  apply_immediately          = true

  # dev is destroyed after every test window: no final snapshot and no deletion protection there.
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name}-db-final"

  performance_insights_enabled = false
  monitoring_interval          = 0

  tags = merge(var.tags, { Name = "${var.name}-db" })
}
