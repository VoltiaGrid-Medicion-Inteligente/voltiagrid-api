variable "name" {
  description = "Prefix for the Name tag of every resource, for example voltiagrid-dev."
  type        = string
}

variable "cidr" {
  description = "CIDR block of the VPC."
  type        = string
}

variable "azs" {
  description = "Availability zones, one public and one private subnet in each."
  type        = list(string)

  validation {
    condition     = length(var.azs) >= 2
    error_message = "At least 2 availability zones are required (RDS and the ALB need them)."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDR of each public subnet, in the same order as azs."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR of each private subnet, in the same order as azs."
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Create one NAT Gateway so the private subnets can reach the internet. Off by default (ADR-011)."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Extra tags for every resource of the module (Component)."
  type        = map(string)
  default     = {}
}