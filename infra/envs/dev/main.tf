# dev stack (ADR-012): everything that is created for a test window and destroyed after it.

locals {
  name = "voltiagrid-${var.environment}"

  # Images deployed to ECS (US-27). Same names as the local images voltiagrid/<name>:local.
  images = [
    "api-customer-consumption",
    "api-control-center",
    "api-network-inventory",
    "api-transformer-metering",
    "migrate-seed",
  ]
}

module "network" {
  source = "../../modules/network"

  name                 = local.name
  cidr                 = var.vpc_cidr
  azs                  = var.azs
  public_subnet_cidrs  = [for i, _ in var.azs : cidrsubnet(var.vpc_cidr, 8, i)]      # 10.20.0.0/24, 10.20.1.0/24
  private_subnet_cidrs = [for i, _ in var.azs : cidrsubnet(var.vpc_cidr, 8, 10 + i)] # 10.20.10.0/24, 10.20.11.0/24
  enable_nat_gateway   = var.enable_nat_gateway

  tags = { Component = "network" }
}

module "security" {
  source = "../../modules/security"

  name              = local.name
  vpc_id            = module.network.vpc_id
  s3_prefix_list_id = module.network.s3_prefix_list_id

  tags = { Component = "security-groups" }
}

module "admin_instance" {
  source = "../../modules/admin_instance"
  count  = var.enable_admin_instance ? 1 : 0

  name                        = local.name
  vpc_id                      = module.network.vpc_id
  subnet_id                   = module.network.private_subnet_ids[0]
  security_group_id           = module.security.admin_sg_id
  endpoints_security_group_id = module.security.endpoints_sg_id

  tags = { Component = "admin-instance" }
}

module "rds" {
  source = "../../modules/rds"

  name               = local.name
  private_subnet_ids = module.network.private_subnet_ids
  security_group_id  = module.security.rds_sg_id
  instance_class     = var.db_instance_class

  tags = { Component = "rds" }
}

module "secrets" {
  source = "../../modules/secrets"

  name = local.name

  tags = { Component = "secrets" }
}

module "ecr" {
  source = "../../modules/ecr"

  repositories = local.images

  tags = { Component = "ecr" }
}

module "logs" {
  source = "../../modules/logs"

  name     = local.name
  services = local.images

  tags = { Component = "logs" }
}

# ---------- ECS (US-27) ----------

locals {
  # Database connection: host, port and name are plain variables; user and password come from the
  # secret that RDS manages (T-25.2). The URL is built in app/core/database_url.py with sslmode=require.
  db_environment = {
    DB_HOST    = module.rds.address
    DB_PORT    = tostring(module.rds.port)
    DB_NAME    = module.rds.db_name
    DB_SSLMODE = "require"
  }
  db_secrets = {
    DB_USER     = "${module.rds.master_secret_arn}:username::"
    DB_PASSWORD = "${module.rds.master_secret_arn}:password::"
  }
  app_secret = module.secrets.app_secret_arn

  # Same variables as docker-compose.yml, without any secret value.
  services = {
    "api-customer-consumption" = {
      port   = 8001
      cpu    = 256
      memory = 512
      environment = merge(local.db_environment, {
        JWT_EXPIRE_MINUTES = "60"
        SIM_SEED           = "42"
        DEFECT_RATE        = "0.02"
      })
      secrets = merge(local.db_secrets, {
        JWT_SECRET             = "${local.app_secret}:jwt_secret::"
        DEMO_CUSTOMER_PASSWORD = "${local.app_secret}:demo_customer_password::"
        DEMO_INTERNAL_PASSWORD = "${local.app_secret}:demo_internal_password::"
      })
    }
    "api-control-center" = {
      port        = 8002
      cpu         = 256
      memory      = 512
      environment = local.db_environment
      secrets     = merge(local.db_secrets, { JWT_SECRET = "${local.app_secret}:jwt_secret::" })
    }
    "api-network-inventory" = {
      port        = 8003
      cpu         = 256
      memory      = 512
      environment = local.db_environment
      secrets     = merge(local.db_secrets, { JWT_SECRET = "${local.app_secret}:jwt_secret::" })
    }
    "api-transformer-metering" = {
      port        = 8005
      cpu         = 256
      memory      = 512
      environment = merge(local.db_environment, { SIM_SEED = "42" })
      secrets     = local.db_secrets
    }
  }

  # One-off job: alembic upgrade head + seed (same image and command as migrate-seed in compose).
  tasks = {
    "migrate-seed" = {
      cpu    = 512
      memory = 1024
      environment = merge(local.db_environment, {
        MODE        = "dev"
        SEED        = "42"
        DEFECT_RATE = "0.02"
      })
      secrets = local.db_secrets
    }
  }
}

module "ecs" {
  source = "../../modules/ecs"

  name              = local.name
  services          = local.services
  tasks             = local.tasks
  image_urls        = module.ecr.repository_urls
  image_tag         = var.image_tag
  desired_count     = var.desired_count
  log_groups        = module.logs.log_group_names
  secret_arns       = [module.rds.master_secret_arn, module.secrets.app_secret_arn]
  subnet_ids        = module.network.public_subnet_ids
  security_group_id = module.security.app_sg_id

  tags = { Component = "ecs", Owner = "p1-backend" }
}
