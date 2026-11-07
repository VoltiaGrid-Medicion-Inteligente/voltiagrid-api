# CI/CD of the applications (US-46)

Every change merged to `main` is tested, built, pushed to ECR and deployed to ECS without manual steps, and a merge
whose tests fail is blocked.

```
pull request -> CI (lint, tests, contracts, secrets, terraform)  -> merge blocked if any check is red
merge to main -> CI again -> build and push the 5 images (tag = short commit) -> deploy the 4 API services
```

## 1. GitHub Actions authenticates with AWS by OIDC (T-46.1)

No AWS access key is stored in GitHub. `infra/bootstrap/github_oidc.tf` creates, once per account:

| Resource | What it allows |
|---|---|
| OIDC provider `token.actions.githubusercontent.com` | AWS trusts the short-lived token GitHub signs for each workflow run |
| Role `voltiagrid-github-deploy` | Assumable **only** by workflows of the `main` branch of `voltiagrid-api` and `voltiagrid-data` (`repo:<org>/<repo>:ref:refs/heads/main`): not by pull requests, other branches or forks. One hour per session |
| Its policy | Push to the `voltiagrid/*` ECR repositories; register task definitions; describe and update the services of `voltiagrid-*` clusters; pass only the `voltiagrid-*` roles, and only to ECS tasks |

Apply it once (admin), then save the role ARN where the workflows read it:

```powershell
aws sso login --profile voltia-admin
$env:AWS_PROFILE = "voltia-admin"
terraform -chdir=infra/bootstrap apply
terraform -chdir=infra/bootstrap output -raw github_deploy_role_arn
```

In GitHub, for `voltiagrid-api` and `voltiagrid-data`: **Settings → Secrets and variables → Actions → Variables →
New repository variable**, name `AWS_DEPLOY_ROLE_ARN`, value the ARN above. It is a variable, not a secret: an ARN
gives nothing without the GitHub token that only the main branch gets.

Check from a workflow run: the step *Configure AWS credentials* prints `Assuming role with OIDC` and the next AWS call
works; from a pull request the same step fails with `Not authorized to perform sts:AssumeRoleWithWebIdentity`.
