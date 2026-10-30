variable "name" {
  description = "Name of the load balancer, for example voltiagrid-dev (max 32 characters)."
  type        = string
}

variable "vpc_id" {
  description = "VPC of the target groups."
  type        = string
}

variable "subnet_ids" {
  description = "Public subnets in at least 2 AZs."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security Group of the load balancer (80 from the internet)."
  type        = string
}

variable "routes" {
  description = "One entry per service: path prefix, container port, rule priority and a short name for the target group."
  type = map(object({
    path_prefix = string
    port        = number
    priority    = number
    short_name  = string
  }))
}

variable "tags" {
  description = "Extra tags (Component)."
  type        = map(string)
  default     = {}
}
