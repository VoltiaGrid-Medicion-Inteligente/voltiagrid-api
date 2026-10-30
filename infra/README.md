# Infrastructure as code (Terraform)

AWS infrastructure of VoltiaGrid (sprint 3, US-21 to US-28). Decisions: ADR-011 (region and network)
and ADR-012 (Terraform, state and stacks) in `voltiagrid-docs`.

## Layout

```
infra/
├── bootstrap/        # S3 bucket for the Terraform state. Applied once, never destroyed.
├── envs/
│   ├── data/         # Persistent stack: data lake buckets (US-23). Not destroyed after a window.
│   └── dev/          # Ephemeral stack: network, endpoints, admin instance, RDS, ECS, ALB...
├── scripts/          # PowerShell helpers: publish images (US-27)
└── modules/          # Reusable pieces used by the stacks
    ├── admin_instance/ # EC2 in a private subnet, Session Manager only (US-22)
    ├── data_lake/    # raw, clean and curated buckets, policies for roles (US-23)
    ├── ecr/          # One image repository per image, immutable tags (US-27)
    ├── logs/         # One CloudWatch log group per service, 7-day retention (US-27)
    ├── network/      # VPC, subnets in 2 AZs, routes, Internet Gateway, optional NAT
    ├── rds/          # PostgreSQL 16, private, encrypted, backups, password in Secrets Manager (US-25)
    ├── secrets/      # JWT secret and demo passwords in Secrets Manager (US-25)
    └── security/     # One Security Group per component, least privilege
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

## The data stack (data lake)

Applied once and kept: it holds the readings for 3 years. A window's `destroy` is only for `envs/dev`.

```powershell
terraform -chdir=infra/envs/data init -backend-config="bucket=$bucket"
terraform -chdir=infra/envs/data plan -out data.tfplan
terraform -chdir=infra/envs/data apply data.tfplan
terraform -chdir=infra/envs/data output
```

`force_destroy` is `false`: a `destroy` of this stack fails while a bucket has objects. That is on purpose.

## How S3 traffic leaves the VPC (T-21.3)

A gateway VPC endpoint for S3 is attached to the public and the private route tables. Each table gets a
route whose destination is the S3 prefix list (`pl-...`) and whose target is the endpoint (`vpce-...`).
Traffic to S3 never uses a NAT Gateway or the internet, and the endpoint has no hourly cost.

Check it after an apply:

```powershell
$vpc = terraform -chdir=infra/envs/dev output -raw vpc_id
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$vpc" --query "RouteTables[].{table:Tags[?Key=='Name']|[0].Value,routes:Routes[].[DestinationCidrBlock||DestinationPrefixListId,GatewayId||NatGatewayId]}" --output json
```

The private table must show only `local` and the `pl-...` route to `vpce-...`, and no `0.0.0.0/0`.

## Tags

The provider applies `Project=voltiagrid`, `Environment`, `Owner` and `ManagedBy=terraform` to every
resource (`default_tags`); each module adds `Component`. Do not remove them: US-28 checks them.
