locals {
  buckets = { for layer in var.layers : layer => "${var.name}-${layer}-${var.account_id}" }
}

resource "aws_s3_bucket" "layer" {
  for_each = local.buckets

  bucket = each.value

  # false in the persistent data stack: a destroy fails if a bucket still has data.
  force_destroy = var.force_destroy

  tags = merge(var.tags, { Name = each.value, Layer = each.key })
}

# ACLs disabled: access is decided only by IAM and the bucket policy.
resource "aws_s3_bucket_ownership_controls" "layer" {
  for_each = aws_s3_bucket.layer

  bucket = each.value.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "layer" {
  for_each = aws_s3_bucket.layer

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Encryption at rest with S3 managed keys (SSE-S3): no cost and no key to manage.
resource "aws_s3_bucket_server_side_encryption_configuration" "layer" {
  for_each = aws_s3_bucket.layer

  bucket = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Raw is the only copy of what the sources sent: versioning protects it from an accidental delete or
# overwrite. Clean and curated are rebuilt from raw by Spark, so they do not pay for old versions.
resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.layer["raw"].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_policy" "layer" {
  for_each = aws_s3_bucket.layer

  bucket = each.value.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [each.value.arn, "${each.value.arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
      {
        # Only IAM roles of this account: no IAM users, no root, no anonymous access.
        # Team members are roles too (AWSReservedSSO_* from IAM Identity Center).
        Sid       = "OnlyRolesOfThisAccount"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [each.value.arn, "${each.value.arn}/*"]
        Condition = {
          StringNotEquals = { "aws:PrincipalType" = "AssumedRole" }
        }
      },
      {
        Sid       = "OnlyThisAccount"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [each.value.arn, "${each.value.arn}/*"]
        Condition = {
          StringNotEquals = { "aws:PrincipalAccount" = var.account_id }
        }
      },
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.layer]
}

# ---------- managed policies to attach to service roles ----------

locals {
  arns       = { for layer, b in aws_s3_bucket.layer : layer => b.arn }
  all_arns   = values(local.arns)
  all_object = [for a in local.all_arns : "${a}/*"]
}

# Read every layer: analysts, Power BI exports, the admin instance if ever needed.
resource "aws_iam_policy" "read" {
  name        = "${var.name}-datalake-read"
  description = "Read every layer of the data lake"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:ListBucket", "s3:GetBucketLocation"], Resource = local.all_arns },
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = local.all_object },
    ]
  })

  tags = var.tags
}

# Write only to raw: ingestion consumers and the initial load (US-29, T-23.3). Cannot delete.
resource "aws_iam_policy" "ingest" {
  name        = "${var.name}-datalake-ingest"
  description = "Write new objects to the raw layer only"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:ListBucket", "s3:GetBucketLocation"], Resource = [local.arns["raw"]] },
      { Effect = "Allow", Action = ["s3:PutObject", "s3:GetObject", "s3:AbortMultipartUpload"], Resource = ["${local.arns["raw"]}/*"] },
    ]
  })

  tags = var.tags
}

# Spark jobs: read raw, read and write clean and curated (US-30 onward).
resource "aws_iam_policy" "process" {
  name        = "${var.name}-datalake-process"
  description = "Read raw; read, write and delete in clean and curated"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:ListBucket", "s3:GetBucketLocation"], Resource = local.all_arns },
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${local.arns["raw"]}/*"] },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
        Resource = [for l in ["clean", "curated"] : "${local.arns[l]}/*"]
      },
    ]
  })

  tags = var.tags
}
