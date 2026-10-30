variable "name" {
  description = "Prefix of the secret name, for example voltiagrid-dev (secret: voltiagrid-dev/app)."
  type        = string
}

variable "tags" {
  description = "Extra tags (Component)."
  type        = map(string)
  default     = {}
}
