output "state_bucket" {
  description = "Bucket to pass to `terraform init -backend-config` in infra/envs/*."
  value       = aws_s3_bucket.state.bucket
}

output "github_deploy_role_arn" {
  description = "Role for GitHub Actions (US-46): save it as the repository variable AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.github_deploy.arn
}
