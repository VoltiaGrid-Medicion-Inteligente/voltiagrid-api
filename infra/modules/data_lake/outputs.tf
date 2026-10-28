output "bucket_names" {
  description = "Bucket name per layer."
  value       = { for layer, b in aws_s3_bucket.layer : layer => b.bucket }
}

output "bucket_arns" {
  value = { for layer, b in aws_s3_bucket.layer : layer => b.arn }
}

output "read_policy_arn" {
  value = aws_iam_policy.read.arn
}

output "ingest_policy_arn" {
  value = aws_iam_policy.ingest.arn
}

output "process_policy_arn" {
  value = aws_iam_policy.process.arn
}
