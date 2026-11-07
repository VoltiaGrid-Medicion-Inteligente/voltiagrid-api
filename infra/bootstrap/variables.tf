variable "region" {
  description = "AWS region of the project (ADR-011)."
  type        = string
  default     = "us-east-1"
}

variable "github_org" {
  description = "GitHub organization of the repositories that deploy (US-46)."
  type        = string
  default     = "VoltiaGrid-Medicion-Inteligente"
}

variable "github_repositories" {
  description = "Repositories whose main branch may push images and deploy: the APIs and the Spark jobs image."
  type        = list(string)
  default     = ["voltiagrid-api", "voltiagrid-data"]
}
