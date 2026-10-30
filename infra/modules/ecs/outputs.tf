output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "service_names" {
  value = [for s in aws_ecs_service.this : s.name]
}

output "task_definition_arns" {
  description = "Task definition ARN (with revision) per image name."
  value       = { for k, td in aws_ecs_task_definition.this : k => td.arn }
}

output "execution_role_arn" {
  value = aws_iam_role.execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}
