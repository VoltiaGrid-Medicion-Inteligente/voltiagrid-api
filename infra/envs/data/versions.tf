terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # Same state bucket as envs/dev, different key (ADR-012):
  #   terraform init -backend-config="bucket=<output state_bucket of infra/bootstrap>"
  backend "s3" {
    key          = "data/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
