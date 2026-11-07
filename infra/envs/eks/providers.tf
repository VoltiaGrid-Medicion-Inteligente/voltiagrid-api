provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "voltiagrid"
      Environment = var.environment
      Owner       = "p3-devops"
      ManagedBy   = "terraform"
      Component   = "eks"
    }
  }
}
