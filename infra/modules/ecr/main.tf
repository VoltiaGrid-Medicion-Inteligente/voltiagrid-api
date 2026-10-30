# Image repositories of US-27 (T-27.1). One repository per image, same names as the local images
# (voltiagrid/<name>:local in docker-compose). Tags are immutable: a tag is a git commit, so the same
# tag always means the same code, and a task definition revision always runs the same image.

resource "aws_ecr_repository" "this" {
  for_each = toset(var.repositories)

  name                 = "voltiagrid/${each.key}"
  image_tag_mutability = "IMMUTABLE"

  # dev is destroyed after every window: delete the repository even if it still has images.
  force_delete = var.force_delete

  image_scanning_configuration {
    scan_on_push = true # basic scan for known vulnerabilities, no cost
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(var.tags, { Name = "voltiagrid/${each.key}" })
}

# Keep the last 10 tagged images and drop untagged layers after a day (storage is 0.10 USD/GB-month).
resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      },
    ]
  })
}
