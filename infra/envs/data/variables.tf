variable "region" {
  description = "AWS region (ADR-011)."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Value of the Environment tag and part of the bucket names."
  type        = string
  default     = "dev"
}

variable "force_destroy" {
  description = "Allow destroying buckets that still have data. Only for the final teardown (US-56)."
  type        = bool
  default     = false
}
