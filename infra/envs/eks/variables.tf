variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  description = "The dev stack whose VPC and RDS the cluster uses."
  type        = string
  default     = "dev"
}

variable "kubernetes_version" {
  description = "EKS version in standard support: 1.35 until 2027-03-27 (check `aws eks describe-cluster-versions`)."
  type        = string
  default     = "1.35"
}

variable "node_instance_type" {
  description = "One small node is enough for the F5 simulator and the system pods (11 pods fit a t3.small)."
  type        = string
  default     = "t3.small"
}

variable "subnet_cidrs" {
  description = "Two public subnets for the nodes, inside the dev VPC (10.20.0.0/16) and outside its own subnets."
  type        = list(string)
  default     = ["10.20.20.0/24", "10.20.21.0/24"]
}

variable "azs" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}
