output "log_group_names" {
  description = "Log group name per service."
  value       = { for service, group in aws_cloudwatch_log_group.this : service => group.name }
}
