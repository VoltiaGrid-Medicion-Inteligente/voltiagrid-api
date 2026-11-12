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

output "lb_arn_suffix" {
  description = "Dimension LoadBalancer of the ALB metrics in CloudWatch (US-63)."
  value       = aws_lb.this.arn_suffix
}

output "target_group_arn_suffixes" {
  description = "Dimension TargetGroup of the ALB metrics in CloudWatch, per service (US-63)."
  value       = { for k, tg in aws_lb_target_group.this : k => tg.arn_suffix }
}
