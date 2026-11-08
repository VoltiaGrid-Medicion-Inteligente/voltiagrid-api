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

## 2. The pipeline (T-46.2)

`.github/workflows/deploy.yml` runs on every push to `main` (a merged pull request) and by hand (**Actions → deploy →
Run workflow**):

| Job | What it does | Fails when |
|---|---|---|
| `ci` | The same checks as a pull request (`ci.yml`, called as a reusable workflow): lint, tests with Postgres and RabbitMQ, OpenAPI contracts, gitleaks, Terraform | Any check fails: nothing is built or deployed |
| `images` | Builds the 5 images (same Dockerfiles as `publish-images.ps1`) and pushes them to ECR with the short commit as tag; a tag already in ECR is kept (immutable tags) | A build or push fails |
| `deploy` | For each of the 4 API services: reads its current task definition, renders a new revision with the new image, registers it, updates the service and waits until it is stable (up to 10 minutes) | The new tasks never become healthy: ECS's circuit breaker rolls the service back to the previous revision and the job ends red |

The run summary lists, per service, the deployed tag and the **previous task definition** (what a manual rollback
goes back to, T-46.3).

**When the dev stack is down** (between test windows) there are no ECR repositories or services: `images` and
`deploy` say so in a notice (`the dev stack is down, nothing to push`) and end green. During a window, merge to
`main` and the APIs are updated without running any script.

**Terraform and the pipeline use the same tag.** The pipeline registers revisions outside Terraform. The next
`terraform apply` of the window must pass the tag the pipeline deployed (`-var image_tag=<short commit of main>`),
or Terraform puts back the image it knows.

### Merges are blocked when a check fails

The `main` and `develop` rulesets require the `lint`, `tests` and `secrets` checks and one approval: GitHub greys out
**Merge** while a required check is red. Evidence for US-46 (one successful and one failed run):

1. **Failed:** a pull request with a test that fails on purpose (for example `assert 1 == 2` in a new test file):
   the `tests` check goes red and the merge button says *Merging is blocked*. Take the screenshot, close the PR
   without merging and delete the branch.
2. **Successful:** a real merge to `main` during a window: the `deploy` run is green with the three jobs, and
   `aws ecs describe-services --cluster voltiagrid-dev --services api-control-center --query "services[0].taskDefinition"`
   shows the new revision.

## 3. Rollback (T-46.3)

Every deployment registers a new revision of the service's task definition and keeps the old ones, so going back is
pointing the service at an earlier revision. There are two ways back, one automatic and one manual:

| | When | What happens |
|---|---|---|
| **Automatic** | The new tasks never become healthy (crash at start, failing health check) | ECS's deployment circuit breaker (on in every service, `infra/modules/ecs`) stops the deployment and returns the service to the last revision that worked; the pipeline's `deploy` job ends red |
| **Manual** | The new version is healthy but wrong (a bug the health check does not see) | `infra/scripts/rollback.ps1` |

```powershell
aws sso login --profile voltia-admin
$env:AWS_PROFILE = "voltia-admin"
.\infra\scripts\rollback.ps1 -Service api-control-center              # to the previous ACTIVE revision
.\infra\scripts\rollback.ps1 -Service api-control-center -Revision 7  # to a given revision (the run summary lists it)
.\infra\scripts\rollback.ps1 -All                                     # the four APIs, each to its previous revision
```

The script prints the revision and image the service runs now and the ones it goes back to, updates the service,
waits until it is stable (ECS replaces tasks one by one, the API keeps answering) and checks `/health` through the
ALB:

```
===== api-control-center
  now:  voltiagrid-dev-api-control-center:7  <account>.dkr.ecr.us-east-1.amazonaws.com/voltiagrid/api-control-center:9c41e2a
  back: voltiagrid-dev-api-control-center:6  <account>.dkr.ecr.us-east-1.amazonaws.com/voltiagrid/api-control-center:3f2a1c9
  waiting until the service is stable ...
  running: voltiagrid-dev-api-control-center:6
  http://<alb>/control-center/health -> ok
```

After a rollback:

1. **Fix forward in git**: revert the bad commit (`git revert <commit>`) in a pull request; when it is merged the
   pipeline deploys a new image with the fix, and the rolled-back revision is no longer needed.
2. **Keep Terraform in line**: the next `terraform apply` of the window takes `-var image_tag=<tag of the revision you
   went back to>`, or Terraform puts back the image it knows.
3. **The database is not rolled back.** A migration that the old code cannot read needs its own downgrade
   (`alembic downgrade -1` in a one-off task) before the rollback; the migrations of sprint 5 only add tables, so
   the old code keeps working with them.

Evidence for US-46: during a window, deploy a change, run `rollback.ps1` for that service and keep its output and the
`describe-services` revision before and after.
