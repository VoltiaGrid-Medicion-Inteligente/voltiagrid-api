output "bucket_name" {
  description = "Bucket where deploy-portal.ps1 uploads the build."
  value       = aws_s3_bucket.site.id
}

output "distribution_id" {
  description = "CloudFront distribution to invalidate after an upload."
  value       = aws_cloudfront_distribution.site.id
}

output "url" {
  description = "Address of the portal: https://<domain>."
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}
