variable "name" {
  description = "Cluster name and prefix of the families and roles, for example voltiagrid-dev."
  type        = string
}

variable "services" {
  description = "Long-running services behind the load balancer, by image name."
  type = map(object({
    port        = number
    cpu         = number
    memory      = number
    environment = map(string)
    secrets     = map(string) # variable name -> Secrets Manager ARN (with :json-key:: suffix)
  }))
}

variable "tasks" {
  description = "One-off tasks (task definition without service), by image name."
  type = map(object({
    cpu         = number
    memory      = number
    environment = map(string)
    secrets     = map(string)
  }))
  default = {}
}

variable "image_urls" {
  description = "ECR repository URL per image name."
  type        = map(string)
}

variable "image_tag" {
  description = "Tag to deploy (short git commit). \"none\" is only valid with desired_count = 0."
  type        = string
}

variable "desired_count" {
  description = "Tasks per service. 0 keeps everything created but stopped."
  type        = number
}

variable "log_groups" {
  description = "CloudWatch log group per image name."
  type        = map(string)
}

variable "secret_arns" {
  description = "Secrets the execution role may read."
  type        = list(string)
}

variable "subnet_ids" {
  description = "Subnets of the tasks (public, ADR-011)."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security Group of the tasks."
  type        = string
}

variable "target_group_arns" {
  description = "Load balancer target group per service (T-27.3). Services not in the map get no load balancer."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Extra tags (Component, Owner)."
  type        = map(string)
  default     = {}
}
