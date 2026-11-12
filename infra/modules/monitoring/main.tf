# Metrics, alarms and notifications of US-63 (T-63.1 dashboard, T-63.2 alarms and SNS).
#
# Only metrics that exist in the dev stack today: the ALB, the ECS services (basic CloudWatch metrics; Container
# Insights is off, see modules/ecs) and RDS. Queue depth and DAG status are not here: there is no queue and no Airflow
# in the AWS stack yet, so there is nothing to read.

data "aws_region" "current" {}

locals {
  region         = data.aws_region.current.name
  alb_metrics    = { LoadBalancer = var.alb_arn_suffix }
  rds_metrics    = { DBInstanceIdentifier = var.rds_identifier }
  ecs_by_service = { for s in var.service_names : s => { ClusterName = var.cluster_name, ServiceName = s } }
}

resource "aws_sns_topic" "alerts" {
  name = "${var.name}-alerts"
  tags = var.tags
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# ---------- Dashboard (T-63.1) ----------

locals {
  ecs_cpu_metrics = [for s in var.service_names : ["AWS/ECS", "CPUUtilization", "ClusterName", var.cluster_name, "ServiceName", s]]

  widgets = [
    {
      type   = "metric"
      x      = 0
      y      = 0
      width  = 12
      height = 6

      properties = {
        title   = "ALB: 5XX responses per 5 min"
        view    = "timeSeries"
        region  = local.region
        period  = 300
        stat    = "Sum"
        metrics = [["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix]]
      }
    },
    {
      type   = "metric"
      x      = 12
      y      = 0
      width  = 12
      height = 6

      properties = {
        title  = "ALB: target response time p95 (RNF-04: at most 0.5 s)"
        view   = "timeSeries"
        region = local.region
        period = 300
        metrics = [
          ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { stat = "p95" }],
        ]
      }
    },
    {
      type   = "metric"
      x      = 0
      y      = 6
      width  = 12
      height = 6

      properties = {
        title   = "ECS: CPU per service (%)"
        view    = "timeSeries"
        region  = local.region
        period  = 300
        stat    = "Average"
        metrics = local.ecs_cpu_metrics
      }
    },
    {
      type   = "metric"
      x      = 12
      y      = 6
      width  = 12
      height = 6

      properties = {
        title  = "RDS: CPU and free storage"
        view   = "timeSeries"
        region = local.region
        period = 300
        metrics = [
          ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_identifier, { stat = "Average", yAxis = "left" }],
          ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", var.rds_identifier, { stat = "Average", yAxis = "right" }],
        ]
      }
    },
  ]
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = "${var.name}-operations"
  dashboard_body = jsonencode({ widgets = local.widgets })
}

# ---------- Alarms (T-63.2) ----------

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.name}-alb-5xx"
  alarm_description   = "The APIs answered 5XX in 5 minutes (US-63)."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  dimensions          = local.alb_metrics
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.error_5xx_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "alb_latency_p95" {
  alarm_name          = "${var.name}-alb-latency-p95"
  alarm_description   = "p95 of the target response time is above RNF-04 (US-63)."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  dimensions          = local.alb_metrics
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 2
  threshold           = var.latency_p95_seconds
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  for_each            = local.ecs_by_service
  alarm_name          = "${var.name}-ecs-cpu-${each.key}"
  alarm_description   = "CPU of ECS service ${each.key} is high for 15 minutes (US-63)."
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  dimensions          = each.value
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = var.ecs_cpu_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.name}-rds-cpu"
  alarm_description   = "CPU of the database is high for 15 minutes (US-63)."
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  dimensions          = local.rds_metrics
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = var.rds_cpu_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "${var.name}-rds-free-storage"
  alarm_description   = "Free storage of the database is below the minimum (US-63)."
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  dimensions          = local.rds_metrics
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.rds_min_free_storage_bytes
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}
