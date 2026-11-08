variable "name" {
  description = "Prefix of every name (voltiagrid-dev)."
  type        = string
}

variable "account_id" {
  description = "AWS account id: the bucket name must be unique across accounts."
  type        = string
}

variable "tags" {
  description = "Extra tags (Component)."
  type        = map(string)
  default     = {}
}
