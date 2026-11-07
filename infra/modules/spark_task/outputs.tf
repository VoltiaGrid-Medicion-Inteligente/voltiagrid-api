output "task_definition_family" {
  value = aws_ecs_task_definition.spark.family
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.spark.arn
}

output "task_role_arn" {
  value = aws_iam_role.spark.arn
}

output "repository_url" {
  value = aws_ecr_repository.spark.repository_url
}

output "log_group" {
  value = aws_cloudwatch_log_group.spark.name
}
