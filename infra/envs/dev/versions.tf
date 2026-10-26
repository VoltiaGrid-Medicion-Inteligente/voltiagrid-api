terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # State in the bucket created by infra/bootstrap (ADR-012). The bucket name has the account id,
  # so it is passed at init time:
  #   terraform init -backend-config="bucket=<output state_bucket of infra/bootstrap>"
  backend "s3" {
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}