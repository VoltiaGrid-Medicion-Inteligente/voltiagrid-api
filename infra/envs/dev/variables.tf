variable "region" {
  description = "AWS region (ADR-011)."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Value of the Environment tag and part of every name."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod (tagging policy)."
  }
}

variable "owner" {
  description = "Default value of the Owner tag (tagging policy)."
  type        = string
  default     = "p3-devops"
}

variable "azs" {
  description = "Availability zones (ADR-011)."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "enable_nat_gateway" {
  description = "Create a NAT Gateway (about 33 USD a month). Off by default (ADR-011)."
  type        = bool
  default     = false
}

variable "enable_admin_instance" {
  description = "Create the admin instance and its SSM endpoints (about 0.035 USD per hour together)."
  type        = bool
  default     = true
}
