variable "name" {
  description = "Prefix of the group names, for example voltiagrid-dev."
  type        = string
}

variable "vpc_id" {
  description = "VPC where the groups are created."
  type        = string
}

variable "s3_prefix_list_id" {
  description = "Prefix list of the S3 gateway endpoint (output of the network module)."
  type        = string
}

variable "app_ports" {
  description = "Container ports of the APIs behind the load balancer."
  type        = list(number)
  default     = [8001, 8002, 8003, 8005]
}

variable "tags" {
  description = "Extra tags for every group (Component)."
  type        = map(string)
  default     = {}
}
