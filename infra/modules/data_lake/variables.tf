variable "name" {
  description = "Prefix of the bucket and policy names, for example voltiagrid-dev."
  type        = string
}

variable "account_id" {
  description = "AWS account id: makes the global bucket names unique and limits access to this account."
  type        = string
}

variable "layers" {
  description = "Layers of the lake (ADR-003). The policies expect raw, clean and curated."
  type        = list(string)
  default     = ["raw", "clean", "curated"]
}

variable "force_destroy" {
  description = "Let terraform destroy delete buckets that still have objects. Keep false outside tests."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Extra tags (Component, Owner)."
  type        = map(string)
    default     = {}
}

variable "retention_days" {
  description = "Days after which every object expires (3 years, US-23)."
  type        = number
  default     = 1095
}