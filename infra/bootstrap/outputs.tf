output "state_bucket" {
  description = "Bucket to pass to `terraform init -backend-config` in infra/envs/*."
  value       = aws_s3_bucket.state.bucket
}
