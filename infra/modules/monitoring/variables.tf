variable "name" {
  description = "Name prefix of the dev stack, e.g. voltiagrid-dev."
  type        = string
}

variable "alb_arn_suffix" {
  description = "LoadBalancer dimension of the ALB (output lb_arn_suffix of modules/alb)."
  type        = string
}

variable "target_group_arn_suffixes" {
  description = "TargetGroup dimension per service (output target_group_arn_suffixes of modules/alb)."
  type        = map(string)
}

variable "cluster_name" {
  description = "ECS cluster name (dimension ClusterName)."
  type        = string
}

variable "service_names" {
  description = "ECS service names (dimension ServiceName). They are the keys of the services of envs/dev."
  type        = list(string)
}

variable "rds_identifier" {
  description = "DB instance identifier (dimension DBInstanceIdentifier), e.g. voltiagrid-dev-db."
  type        = string
}

variable "alarm_email" {
  description = "Address that receives the alarms. Empty creates the topic without a subscription. AWS sends a confirmation mail that must be accepted."
  type        = string
  default     = ""
}

variable "error_5xx_threshold" {
  description = "5XX responses of the ALB in 5 minutes that raise the alarm."
  type        = number
  default     = 5
}

variable "latency_p95_seconds" {
  description = "p95 of the target response time that raises the alarm. RNF-04 asks for p95 of 500 ms or less."
  type        = number
  default     = 0.5
}

variable "ecs_cpu_threshold" {
  description = "CPU percent of an ECS service over 3 periods of 5 minutes that raises the alarm."
  type        = number
  default     = 85
}

variable "rds_cpu_threshold" {
  description = "CPU percent of RDS over 3 periods of 5 minutes that raises the alarm."
  type        = number
  default     = 80
}

variable "rds_min_free_storage_bytes" {
  description = "Free storage of RDS below which the alarm is raised (default 2 GiB)."
  type        = number
  default     = 2147483648
}

variable "tags" {
  description = "Tags of the resources of this module."
  type        = map(string)
  default     = {}
}
