terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # Same state bucket as envs/dev, its own key (ADR-012). Created only for the ECS vs EKS comparison (US-50) and
  # destroyed at the end of each window, before envs/dev:
  #   terraform init -backend-config="bucket=<output state_bucket of infra/bootstrap>"
  backend "s3" {
    key          = "eks/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
