# Admin instance of US-22 (T-22.1). Purpose (ADR-013): a door into the private network for admin
# tasks (port forwarding to RDS, checking S3 through the endpoint) without opening SSH.
#
# - Private subnet, no public IP, no key pair, Security Group with no inbound rules.
# - Access only through AWS Systems Manager Session Manager. Without a NAT Gateway the agent
#   reaches SSM through three interface endpoints placed in one AZ (about 0.03 USD per hour).

data "aws_region" "current" {}

# Provider default tags (Project, Environment, Owner): the root disk does not inherit them by itself.
data "aws_default_tags" "current" {}

# Latest Amazon Linux 2023 for ARM (Graviton). The SSM agent comes preinstalled.
data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

# ---------- IAM: the instance may only talk to Systems Manager ----------

resource "aws_iam_role" "this" {
  name        = "${var.name}-admin-instance"
  description = "Admin instance: Session Manager access only"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "this" {
  name = "${var.name}-admin-instance"
  role = aws_iam_role.this.name

  tags = var.tags
}

# ---------- the instance ----------

resource "aws_instance" "this" {
  ami                         = data.aws_ssm_parameter.al2023_arm64.value
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [var.security_group_id]
  iam_instance_profile        = aws_iam_instance_profile.this.name
  associate_public_ip_address = false
  # No key_name: there is no SSH key. Access is Session Manager only.

  metadata_options {
    http_tokens   = "required" # IMDSv2 only
    http_endpoint = "enabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    encrypted             = true
    delete_on_termination = true
  }

  volume_tags = merge(data.aws_default_tags.current.tags, var.tags, { Name = "${var.name}-admin-root" })

  # A new AMI version must not replace the instance on every plan.
  lifecycle {
    ignore_changes = [ami]
  }

  tags = merge(var.tags, { Name = "${var.name}-admin" })

  depends_on = [aws_vpc_endpoint.ssm]
}

# ---------- interface endpoints for Session Manager ----------

resource "aws_vpc_endpoint" "ssm" {
  for_each = toset(["ssm", "ssmmessages", "ec2messages"])

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [var.subnet_id] # one AZ only, to pay for one network interface per endpoint
  security_group_ids  = [var.endpoints_security_group_id]
  private_dns_enabled = true

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })
}
