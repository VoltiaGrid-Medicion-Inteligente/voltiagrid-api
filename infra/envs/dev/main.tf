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
