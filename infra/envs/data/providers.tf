provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "voltiagrid"
      Environment = var.environment
      Owner       = "p2-data"
      ManagedBy   = "terraform"
    }
  }
}
