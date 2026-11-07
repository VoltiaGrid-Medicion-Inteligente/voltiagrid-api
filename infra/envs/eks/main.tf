# EKS for the ECS vs EKS comparison (US-50, T-50.1; ADR-014: the F5 simulator is the EKS component).
#
# Ephemeral like dev and smaller: one control plane and one t3.small node in a managed node group, inside the dev
# VPC so the F5 pod reaches the same RDS. The nodes get their own two public subnets (public IP, no NAT, ADR-011):
# the dev subnets do not give public IPs on launch, and changing them would change the dev network for everything
# else. Create it after envs/dev and destroy it before (infra/scripts/destroy-eks.ps1, T-50.4).

locals {
  name = "voltiagrid-${var.environment}-eks"
}

data "aws_vpc" "dev" {
  tags = { Name = "voltiagrid-${var.environment}" }
}

data "aws_route_table" "public" {
  vpc_id = data.aws_vpc.dev.id
  tags   = { Name = "voltiagrid-${var.environment}-public" }
}

data "aws_security_group" "rds" {
  vpc_id = data.aws_vpc.dev.id
  name   = "voltiagrid-${var.environment}-rds"
}

resource "aws_subnet" "nodes" {
  count = length(var.azs)

  vpc_id                  = data.aws_vpc.dev.id
  cidr_block              = var.subnet_cidrs[count.index]
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = true # nodes pull images and join the cluster over the internet (no NAT)

  tags = { Name = "${local.name}-nodes-${substr(var.azs[count.index], -1, 1)}" }
}

resource "aws_route_table_association" "nodes" {
  count = length(var.azs)

  subnet_id      = aws_subnet.nodes[count.index].id
  route_table_id = data.aws_route_table.public.id
}

# ---------- IAM ----------

resource "aws_iam_role" "cluster" {
  name = "${local.name}-cluster"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "eks.amazonaws.com" }, Action = ["sts:AssumeRole", "sts:TagSession"] }]
  })
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "nodes" {
  name = "${local.name}-nodes"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "nodes" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly", # pull the F5 image from ECR
  ])

  role       = aws_iam_role.nodes.name
  policy_arn = each.value
}

# ---------- cluster and nodes ----------

resource "aws_eks_cluster" "this" {
  name     = local.name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  # Never bill extended support (0.60 USD/hour instead of 0.10): when the version leaves standard support, AWS
  # upgrades the cluster instead of moving it to extended support.
  upgrade_policy {
    support_type = "STANDARD"
  }

  vpc_config {
    subnet_ids              = aws_subnet.nodes[*].id
    endpoint_public_access  = true # kubectl from the laptops
    endpoint_private_access = true # the nodes talk to the API inside the VPC
  }

  # Access entries instead of the aws-auth ConfigMap; whoever creates the cluster is its admin.
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }

  depends_on = [aws_iam_role_policy_attachment.cluster]
}

resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "default"
  node_role_arn   = aws_iam_role.nodes.arn
  subnet_ids      = aws_subnet.nodes[*].id
  instance_types  = [var.node_instance_type]
  capacity_type   = "ON_DEMAND"
  ami_type        = "AL2023_x86_64_STANDARD" # Amazon Linux 2 nodes are not available from Kubernetes 1.33 on

  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 2
  }

  update_config {
    max_unavailable = 1
  }

  tags = { Name = "${local.name}-node" }

  depends_on = [aws_iam_role_policy_attachment.nodes, aws_route_table_association.nodes]
}

# The F5 pod reads F4 from the dev RDS: open 5432 from the cluster's security group (nodes and pods use it).
resource "aws_vpc_security_group_ingress_rule" "rds_from_eks" {
  security_group_id            = data.aws_security_group.rds.id
  referenced_security_group_id = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL from the EKS nodes (US-50)"
}
