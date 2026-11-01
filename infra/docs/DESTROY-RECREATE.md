# Destroy and recreate test (US-28, T-28.2)

Goal: prove that the whole `dev` environment can be destroyed and created again **with no manual step**, and
that nothing billable is left after a destroy (avoids hidden costs and the 10% penalty).

The data lake (`infra/envs/data`) and the state bucket (`infra/bootstrap`) are persistent by design (ADR-012) and
are not part of this test. Their final teardown is US-56.

## The two scripts

| Script | What it does |
|---|---|
| `infra/scripts/deploy.ps1` | init → infrastructure without tasks → images to ECR → task definitions with the commit tag → migrations and seed in RDS → services with 1 task → health of the 4 APIs through the ALB → tag check. Prints the time of each step. |
| `infra/scripts/destroy.ps1` | `terraform destroy` of dev, then asks AWS for anything that bills per hour (EC2, RDS, ALB, NAT, Elastic IPs, endpoints, ECS cluster). Fails if something is left. |

Both find the state bucket on their own (`voltiagrid-tfstate-<account id>`), so they work from any team laptop.

## Procedure

From the root of `voltiagrid-api`, on `develop` up to date and with no local changes, Docker Desktop running:

```powershell
aws sso login --profile voltia-admin
$env:AWS_PROFILE = "voltia-admin"

# Round 1: create from nothing
.\infra\scripts\deploy.ps1 -AutoApprove

# Destroy everything
.\infra\scripts\destroy.ps1 -AutoApprove

# Round 2: create again, same commands, no manual step in between
.\infra\scripts\deploy.ps1 -AutoApprove

# Same infrastructure as the code: nothing to change
terraform -chdir=infra/envs/dev plan -var "image_tag=$(git rev-parse --short HEAD)" -detailed-exitcode

# End of the window
.\infra\scripts\destroy.ps1 -AutoApprove
```

`plan -detailed-exitcode` must end with *No changes* (exit code 0).

## Result

- **Date:** 2026-11-01
- **Run by:** Mary Muñoz
- **Commit:** a2f7026

| Step | Round 1 (min) | Round 2 (min) |
|---|---|---|
| 1. terraform init | 0.3 | 0.2 |
| 2. infrastructure, no tasks | 10 | 10 |
| 3. images to ECR | 4.8 | 5.9 |
| 4a. task definitions | 0.8 | 0.5 |
| 4b. migrations and seed in RDS | 1.7 | 1.3 |
| 5. services running | 1.8 | 1.4 |
| 6. health through the ALB and tags | 0.8 | 0.4 |
| **Total deploy** | **20.2** | **19.7** |
| `terraform destroy` | 7 | 5.9 |

| Check | Result |
|---|---|
| Round 1: the 4 `/health` answer `ok` through the ALB | Yes (4/4) |
| Round 1: `check_tags` says `OK` | Yes (128 resources, 0 problems) |
| Destroy: `destroy.ps1` ends with *Nothing billable left in dev* | Yes |
| Round 2: same as round 1, without touching anything by hand | Yes (4/4 health, tags OK: 211 resources, 0 problems) |
| `plan -var image_tag=a2f7026` after round 2: *No changes* | Yes |
| Final destroy: nothing left | Yes (*Nothing billable left in dev*) |
| Manual steps needed | none |

Paste the console output of both rounds and both destroys in the pull request.

## Known waits

- RDS takes 5 to 10 minutes to create and 5 to 8 to delete; it is most of the time of step 2 and of the destroy.
- Round 2 republishes the images: the ECR repositories were deleted in the destroy (`force_delete = true`).
- Secrets are deleted without a recovery window (`recovery_window_in_days = 0`), so round 2 can reuse the same names right away.
