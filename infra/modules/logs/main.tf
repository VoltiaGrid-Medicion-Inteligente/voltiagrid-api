# Centralized logs of US-27 (T-27.4). One CloudWatch log group per container image. Every container
# writes to stdout/stderr and ECS sends it here with the awslogs driver (T-27.2); uvicorn's access log
# gives one line per request.

resource "aws_cloudwatch_log_group" "this" {
  for_each = toset(var.services)

  name              = "/ecs/${var.name}/${each.key}"
  retention_in_days = var.retention_days

  tags = merge(var.tags, { Name = "/ecs/${var.name}/${each.key}" })
}
