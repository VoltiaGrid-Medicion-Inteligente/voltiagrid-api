variable "name" {
  description = "Prefix of the names, for example voltiagrid-dev."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnets in at least 2 AZs (DB subnet group)."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security Group of the database (5432 only from the tasks and the admin instance)."
  type        = string
}

variable "instance_class" {
  description = "db.t4g.micro in dev (docs: Costs)."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "GB of gp3 storage (20 is the minimum)."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Database created at start, same name as in docker-compose."
  type        = string
  default     = "voltiagrid"
}

variable "username" {
  description = "Master user. Its password lives only in Secrets Manager."
  type        = string
  default     = "voltia"
}

variable "deletion_protection" {
  description = "true outside dev."
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "true in dev, where the data is rebuilt by the seed in every window."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Extra tags (Component)."
  type        = map(string)
  default     = {}
}
