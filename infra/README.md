# Infrastructure as code (Terraform)

AWS infrastructure of VoltiaGrid (sprint 3, US-21 to US-28). Decisions: ADR-011 (region and network)
and ADR-012 (Terraform, state and stacks) in `voltiagrid-docs`.

## Layout

```
infra/
├── bootstrap/        # S3 bucket for the Terraform state. Applied once, never destroyed.
├── envs/
│   └── dev/          # Ephemeral stack: network, endpoints, admin instance, RDS, ECS, ALB...
└── modules/          # Reusable pieces used by the stacks
    └── network/      # VPC, subnets in 2 AZs, routes, Internet Gateway, optional NAT
```

## Prerequisites (Windows, once)

| Tool | Install | Check |
|---|---|---|
| Terraform 1.10 or later | `winget install Hashicorp.Terraform` (open a new terminal after) | `terraform version` |
| AWS CLI v2 | `winget install Amazon.AWSCLI` | `aws --version` |
| Session Manager plugin (admin instance, US-22) | `winget install Amazon.SessionManagerPlugin` | `session-manager-plugin` |

Applying needs the `voltia-admin` profile (permission set `VoltiaAdmin`): the stacks create IAM roles,
which `VoltiaDeveloper` cannot do. Writing code, `fmt` and `validate` need no AWS access at all.

```powershell
aws sso login --profile voltia-admin
$env:AWS_PROFILE = "voltia-admin"
aws sts get-caller-identity
```

## Check the code without AWS (every pull request)

```powershell
terraform fmt -recursive infra
terraform -chdir=infra/envs/dev init -backend=false
terraform -chdir=infra/envs/dev validate
```

CI runs the same checks in the `terraform` job.

## Cost rules (about 110 USD of credits for the whole project)

1. **Develop locally.** AWS is only for test windows (US-21 review, data load, deployment, destroy and recreate test).
2. **Every window ends with `terraform destroy`** of `envs/dev`. Nothing is left running overnight.
3. Before applying, read the plan: no NAT Gateway (`enable_nat_gateway = false`), no instance bigger than the defaults.
4. If a budget alert arrives, run `terraform destroy` first and investigate after.

## First time only: the state bucket

```powershell
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply
terraform -chdir=infra/bootstrap output -raw state_bucket
```

Keep `infra/bootstrap/terraform.tfstate` (it is git-ignored). The bucket has `prevent_destroy`.

## Apply and destroy the dev stack

```powershell
$bucket = terraform -chdir=infra/bootstrap output -raw state_bucket   # or ask whoever applied the bootstrap
terraform -chdir=infra/envs/dev init -backend-config="bucket=$bucket"
terraform -chdir=infra/envs/dev plan -out dev.tfplan
terraform -chdir=infra/envs/dev apply dev.tfplan
# ... test ...
terraform -chdir=infra/envs/dev destroy
```

## Tags

The provider applies `Project=voltiagrid`, `Environment`, `Owner` and `ManagedBy=terraform` to every
resource (`default_tags`); each module adds `Component`. Do not remove them: US-28 checks them.
