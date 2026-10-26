provider "aws" {
  region = var.region

  # Tagging policy (docs: AWS account and access). Every resource gets these tags;
  # modules add Component and may override Owner.
  default_tags {
    tags = {
      Project     = "voltiagrid"
      Environment = var.environment
      Owner       = var.owner
      ManagedBy   = "terraform"
    }
  }
}
