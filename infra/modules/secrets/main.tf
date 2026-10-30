# Application secrets of US-25 (T-25.2): the JWT signing key and the two demo passwords, generated at
# random and stored in Secrets Manager. ECS injects them into the containers as environment variables
# (T-27.2); they are never written in the repo, in .env files of the cloud or in the task definition.
#
# The values are also kept in the Terraform state, which is encrypted in the state bucket and only
# readable by admins (ADR-012).

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    random = {
      source = "hashicorp/random"
    }
  }
}

resource "random_password" "jwt_secret" {
  length  = 48
  special = false
}

resource "random_password" "demo" {
  for_each = toset(["customer", "internal"])

  length  = 20
  special = false
}

resource "aws_secretsmanager_secret" "app" {
  name        = "${var.name}/app"
  description = "VoltiaGrid APIs: JWT secret and demo passwords"

  # dev is destroyed and recreated often: delete at once instead of the default 7-30 day wait,
  # so the same name can be created again on the next apply.
  recovery_window_in_days = 0

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id

  secret_string = jsonencode({
    jwt_secret             = random_password.jwt_secret.result
    demo_customer_password = random_password.demo["customer"].result
    demo_internal_password = random_password.demo["internal"].result
  })
}
