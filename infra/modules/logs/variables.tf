variable "name" {
  description = "Prefix of the log group names, for example voltiagrid-dev."
  type        = string
}

variable "services" {
  description = "One log group per service (container image name)."
  type        = list(string)
}

variable "retention_days" {
  description = "Days the logs are kept. 7 is enough for dev windows; storage is 0.03 USD/GB-month."
  type        = number
  default     = 7
}

variable "tags" {
  description = "Extra tags (Component)."
  type        = map(string)
  default     = {}
}
