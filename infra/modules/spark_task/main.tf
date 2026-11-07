# Spark jobs on ECS Fargate (US-40, T-40.2; ADR-002 and ADR-014). One task definition for every Spark job of
# voltiagrid-data: the image (docker/spark/Dockerfile there) and its size are the same, only the command changes,
# and Airflow (or infra/scripts/run-spark.ps1) passes it when it starts the task.
#
# - Its own task role: read raw, read and write clean and curated (the data lake "process" policy). The APIs keep a
#   role without permissions.
# - Its own ECR repository and log group, like the images of US-27.
# - The lake buckets reach the jobs as LAKE_RAW, LAKE_CLEAN and LAKE_CURATED (s3a:// URIs); credentials come from the
#   task role, never from variables.

data "aws_region" "current" {}

resource "aws_ecr_repository" "spark" {
  name                 = "voltiagrid/spark-jobs"
  image_tag_mutability = "IMMUTABLE" # a tag is a git commit of voltiagrid-data
  force_delete         = var.force_delete

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(var.tags, { Name = "voltiagrid/spark-jobs" })
}

# The image is about 1.5 GB (AWS SDK bundle of the S3A connector): keep only the last 5.
resource "aws_ecr_lifecycle_policy" "spark" {
  repository = aws_ecr_repository.spark.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove untagged images after 1 day"
        selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 1 }
        action       = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the last 5 images"
        selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
        action       = { type = "expire" }
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "spark" {
  name              = "/ecs/${var.name}/spark-jobs"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, { Name = "/ecs/${var.name}/spark-jobs" })
}

resource "aws_iam_role" "spark" {
  name        = "${var.name}-spark-task"
  description = "Spark jobs: read raw, read and write clean and curated"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "process" {
  role       = aws_iam_role.spark.name
  policy_arn = var.lake_process_policy_arn
}

resource "aws_ecs_task_definition" "spark" {
  family                   = "${var.name}-spark-jobs"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = aws_iam_role.spark.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  # Spark writes its shuffle files to /tmp: 21 GB is the free ephemeral storage of a Fargate task; ask for more only
  # if the history load (US-41) needs it.
  ephemeral_storage {
    size_in_gib = var.ephemeral_storage_gib
  }

  container_definitions = jsonencode([{
    name      = "spark-jobs"
    image     = "${aws_ecr_repository.spark.repository_url}:${var.image_tag}"
    essential = true
    command   = ["python", "docker/spark/check_image.py"] # replaced by the job when the task is started
    environment = [
      { name = "AWS_REGION", value = data.aws_region.current.name },
      { name = "LAKE_RAW", value = "s3a://${var.lake_buckets["raw"]}" },
      { name = "LAKE_CLEAN", value = "s3a://${var.lake_buckets["clean"]}" },
      { name = "LAKE_CURATED", value = "s3a://${var.lake_buckets["curated"]}" },
      { name = "SPARK_DRIVER_MEMORY", value = "${floor(var.memory * 0.75 / 1024)}g" }, # the rest for Python and the JVM
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.spark.name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "spark-jobs"
      }
    }
  }])

  tags = merge(var.tags, { Name = "${var.name}-spark-jobs" })
}
