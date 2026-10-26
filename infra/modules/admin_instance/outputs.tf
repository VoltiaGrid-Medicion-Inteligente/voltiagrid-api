output "instance_id" {
  description = "Use it with aws ssm start-session --target <instance_id>."
  value       = aws_instance.this.id
}

output "role_name" {
  value = aws_iam_role.this.name
}
