output "repository_urls" {
  description = "Repository URL per image name."
  value       = { for name, repo in aws_ecr_repository.this : name => repo.repository_url }
}
