variable "name" {
  description = "Prefix of the names, for example voltiagrid-dev."
  type        = string
}

variable "vpc_id" {
  description = "VPC of the endpoints."
  type        = string
}

variable "subnet_id" {
  description = "Private subnet for the instance and the SSM endpoints."
  type        = string
}

variable "security_group_id" {
  description = "Security Group of the instance (no inbound rules)."
  type        = string
}

variable "endpoints_security_group_id" {
  description = "Security Group of the SSM interface endpoints."
  type        = string
}

variable "instance_type" {
  description = "Smallest Graviton instance is enough for the SSM agent and port forwarding."
  type        = string
  default     = "t4g.nano"
}

variable "tags" {
  description = "Extra tags (Component)."
  type        = map(string)
  default     = {}
}
