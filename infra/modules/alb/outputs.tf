output "dns_name" {
  value = aws_lb.this.dns_name
}

output "url" {
  description = "Base URL of the APIs: <url>/consumption, <url>/control-center, <url>/inventory, <url>/f5."
  value       = "http://${aws_lb.this.dns_name}"
}

output "target_group_arns" {
  description = "Target group ARN per service, for the ECS services."
  value       = { for k, tg in aws_lb_target_group.this : k => tg.arn }
}
