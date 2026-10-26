# dev stack (ADR-012): everything that is created for a test window and destroyed after it.

locals {
  name = "voltiagrid-${var.environment}"
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
