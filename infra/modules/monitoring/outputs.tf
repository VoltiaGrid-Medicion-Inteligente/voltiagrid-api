output "alerts_topic_arn" {
  description = "SNS topic that every alarm publishes to."
  value       = aws_sns_topic.alerts.arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard with the operations widgets (US-63, T-63.1)."
  value       = aws_cloudwatch_dashboard.this.dashboard_name
}

output "alarm_names" {
  description = "Names of the alarms of the dev stack (US-63, T-63.2)."
  value = [
    aws_cloudwatch_metric_alarm.alb_5xx.alarm_name,
    aws_cloudwatch_metric_alarm.alb_latency_p95.alarm_name,
    aws_cloudwatch_metric_alarm.rds_cpu.alarm_name,
    aws_cloudwatch_metric_alarm.rds_free_storage.alarm_name,
  ]
}

output "ecs_cpu_alarm_names" {
  description = "Names of the per-service ECS CPU alarms (US-63, T-63.2)."
  value       = [for a in aws_cloudwatch_metric_alarm.ecs_cpu : a.alarm_name]
}
