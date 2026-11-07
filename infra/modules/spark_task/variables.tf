variable "name" {
  description = "Prefix of the resources, e.g. voltiagrid-dev."
  type        = string
}

variable "execution_role_arn" {
  description = "ECS execution role (pull from ECR, write logs), shared with the APIs."
  type        = string
}

variable "lake_process_policy_arn" {
  description = "Data lake policy for Spark: read raw, read and write clean and curated (infra/envs/data)."
  type        = string
}

variable "lake_buckets" {
  description = "Bucket name per layer: raw, clean, curated."
  type        = map(string)
}

variable "image_tag" {
  description = "Tag of voltiagrid/spark-jobs to run (short git commit of voltiagrid-data)."
  type        = string
}

variable "cpu" {
  description = "Task CPU units: 2048 = 2 vCPU. Airflow can ask for more per run (history load)."
  type        = number
  default     = 2048
}

variable "memory" {
  description = "Task memory in MiB: 8192 = 8 GB."
  type        = number
  default     = 8192
}

variable "ephemeral_storage_gib" {
  description = "Disk for Spark's scratch files (21 GiB is included in the price of a Fargate task)."
  type        = number
  default     = 21
}

variable "log_retention_days" {
  type    = number
  default = 7
}

variable "force_delete" {
  description = "Delete the ECR repository with its images on destroy (dev is destroyed after every window)."
  type        = bool
  default     = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
