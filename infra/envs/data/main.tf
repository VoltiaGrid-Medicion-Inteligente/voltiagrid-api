data "aws_caller_identity" "current" {}

module "data_lake" {
  source = "../../modules/data_lake"

  name          = "voltiagrid-${var.environment}"
  account_id    = data.aws_caller_identity.current.account_id
  force_destroy = var.force_destroy

  tags = { Component = "data-lake" }
}
