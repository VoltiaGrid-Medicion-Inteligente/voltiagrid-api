# GitHub Actions -> AWS without stored keys (US-46, T-46.1; ADR-009 identity).
#
# GitHub signs a short-lived token for every workflow run; AWS trusts it through this OIDC provider and lets the run
# assume the deploy role for one hour. Only workflows of the main branch of the listed repositories can assume it:
# a pull request, another branch or a fork cannot. No AWS access key is stored in GitHub.
#
# It lives in bootstrap (applied once, never destroyed) because the provider is one per account and the role must
# exist before the dev stack is created in a window.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # AWS validates GitHub's certificate with its own trusted CAs; the thumbprints are kept for older provider versions.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1", "1c58a3a8518e8759bf075b76b750d4f2df264fcd"]
}

locals {
  deploy_subjects = [for repo in var.github_repositories : "repo:${var.github_org}/${repo}:ref:refs/heads/main"]
}

resource "aws_iam_role" "github_deploy" {
  name                 = "voltiagrid-github-deploy"
  description          = "GitHub Actions on main: push images to ECR and deploy them to ECS (US-46)"
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike   = { "token.actions.githubusercontent.com:sub" = local.deploy_subjects }
      }
    }]
  })
}

data "aws_region" "current" {}

resource "aws_iam_role_policy" "github_deploy" {
  name = "push-images-and-deploy"
  role = aws_iam_role.github_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrLogin"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "EcrPushVoltiagridRepositories"
        Effect = "Allow"
        # DescribeRepositories: the workflows check that the repository exists (dev stack up) before pushing
        Action = ["ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:CompleteLayerUpload",
          "ecr:DescribeImages", "ecr:DescribeRepositories", "ecr:InitiateLayerUpload", "ecr:PutImage",
        "ecr:UploadLayerPart"]
        Resource = "arn:aws:ecr:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:repository/voltiagrid/*"
      },
      {
        Sid      = "EcsTaskDefinitions"
        Effect   = "Allow"
        Action   = ["ecs:DescribeTaskDefinition", "ecs:RegisterTaskDefinition"]
        Resource = "*" # these two actions do not support resource-level permissions
      },
      {
        Sid    = "EcsVoltiagridServices"
        Effect = "Allow"
        Action = ["ecs:DescribeClusters", "ecs:DescribeServices", "ecs:UpdateService"]
        Resource = [
          "arn:aws:ecs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:cluster/voltiagrid-*",
          "arn:aws:ecs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:service/voltiagrid-*/*",
        ]
      },
      {
        Sid       = "PassOnlyTheEcsRoles"
        Effect    = "Allow"
        Action    = ["iam:PassRole"]
        Resource  = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/voltiagrid-*"
        Condition = { StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" } }
      },
    ]
  })
}
