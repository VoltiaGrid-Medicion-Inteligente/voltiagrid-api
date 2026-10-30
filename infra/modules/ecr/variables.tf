variable "repositories" {
  description = "Image names without the voltiagrid/ prefix."
  type        = list(string)
}

variable "force_delete" {
  description = "Delete repositories with images on destroy (true in dev)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Extra tags (Component)."
  type        = map(string)
  default     = {}
}
