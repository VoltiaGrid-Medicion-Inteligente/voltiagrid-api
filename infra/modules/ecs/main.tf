# ECS Fargate of US-27 (T-27.2): one cluster, one task definition per image, one service per API and a
# task definition without service for the one-off migrations + seed job.
#
# - Every apply with a new image_tag creates a new task definition revision (versioned deployments).
# - Tasks run in the public subnets with a public IP (ADR-011); their Security Group only accepts
#   traffic from the load balancer.
# - Secrets come from Secrets Manager through the execution role; nothing secret is in the definition.

data "aws_region" "current" {}

locals {
  # Size of every task definition: services and one-off tasks.
  sizes = merge(
    { for k, v in var.services : k => { cpu = v.cpu, memory = v.memory } },
    { for k, v in var.tasks : k => { cpu = v.cpu, memory = v.memory } },
  )

  # Part of the container definition shared by services and one-off tasks.
  base_container = { for k, v in merge(var.services, var.tasks) : k => {
    name        = k
    image       = "${var.image_urls[k]}:${var.image_tag}"
    essential   = true
    environment = [for name in sort(keys(v.environment)) : { name = name, value = v.environment[name] }]
    secrets     = [for name in sort(keys(v.secrets)) : { name = name, valueFrom = v.secrets[name] }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = var.log_groups[k]
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = k
      }
    }
  } }

  # Services also expose a port and have a container health check (same check as the Dockerfiles).
  containers = merge(
    { for k, v in var.services : k => jsonencode([merge(local.base_container[k], {
      portMappings = [{ containerPort = v.port, protocol = "tcp" }]
      healthCheck = {
        command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:${v.port}/health', timeout=2)"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    })]) },
    { for k, v in var.tasks : k => jsonencode([local.base_container[k]]) },
  )
}

resource "aws_ecs_cluster" "this" {
  name = var.name

  # Container Insights costs per metric; basic CloudWatch metrics are enough for dev (US-63 decides).
  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = var.tags
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# ---------- IAM ----------

locals {
  ecs_tasks_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Execution role: used by ECS itself to pull the image, write logs and read the secrets at start.
resource "aws_iam_role" "execution" {
  name               = "${var.name}-ecs-execution"
  description        = "ECS: pull images from ECR, write CloudWatch logs, read the app and RDS secrets"
  assume_role_policy = local.ecs_tasks_trust

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "read-app-secrets"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = var.secret_arns
    }]
  })
}

# Task role: what the code inside the container may do in AWS. The APIs call no AWS service,
# so it has no policies (least privilege). Spark and ingestion roles will get the data lake policies.
resource "aws_iam_role" "task" {
  name               = "${var.name}-ecs-task"
  description        = "Role of the application containers: no AWS permissions"
  assume_role_policy = local.ecs_tasks_trust

  tags = var.tags
}

# ---------- task definitions ----------

resource "aws_ecs_task_definition" "this" {
  for_each = local.sizes

  family                   = "${var.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64" # images are built on x86 laptops (docs: Costs, G4)
  }

  container_definitions = local.containers[each.key]

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })
}

# ---------- services ----------

resource "aws_ecs_service" "this" {
  for_each = var.services

  name            = each.key
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this[each.key].arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = true # no NAT Gateway (ADR-011); the Security Group blocks inbound traffic
  }

  # A deployment whose tasks never become healthy is stopped and rolled back to the last good revision.
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  dynamic "load_balancer" {
    for_each = contains(keys(var.target_group_arns), each.key) ? [var.target_group_arns[each.key]] : []

    content {
      target_group_arn = load_balancer.value
      container_name   = each.key
      container_port   = each.value.port
    }
  }

  health_check_grace_period_seconds = contains(keys(var.target_group_arns), each.key) ? 60 : null

  propagate_tags        = "SERVICE"
  wait_for_steady_state = false

  tags = merge(var.tags, { Name = each.key })

  lifecycle {
    precondition {
      condition     = var.desired_count == 0 || var.image_tag != "none"
      error_message = "Set -var image_tag=<git short commit> (published with infra/scripts/publish-images.ps1), or use -var desired_count=0."
    }
  }
}
