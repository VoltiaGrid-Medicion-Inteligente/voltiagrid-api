# Tag verification (US-28, T-28.1)

Tagging policy (docs: *AWS account and access*): every resource that supports tags has

| Tag | Allowed values | Set by |
|---|---|---|
| `Project` | `voltiagrid` | provider `default_tags` |
| `Environment` | `dev`, `prod` (`shared` for the state bucket) | provider `default_tags` |
| `Owner` | `p1-backend`, `p2-data`, `p3-devops`, `p4-analytics` | provider `default_tags`, overridden per module (ECS: `p1-backend`, data lake: `p2-data`) |
| `Component` | short free text (`network`, `rds`, `alb`...) | each module call |
| `ManagedBy` | `terraform` | provider `default_tags` (informative, not checked) |

## The script

`scripts/check_tags.py` checks the four required tags and their values. It exits with code 1 if any resource
breaks the policy, so it can run in CI or at the end of a deployment window.

```powershell
python -m pip install -r requirements-dev.txt     # boto3 for --aws

# 1. Terraform state: every resource Terraform manages, including the ones that would not show up as tagged
python -m scripts.check_tags --stack infra/envs/dev --stack infra/envs/data --stack infra/bootstrap

# 2. Live account: everything tagged Project=voltiagrid, as AWS sees it (includes tags added by hand)
python -m scripts.check_tags --aws
```

Expected output, one block per source and a final line:

```
infra/envs/dev: 75 resources checked, 18 without tag support, 0 with problems
infra/envs/data: 6 resources checked, 16 without tag support, 0 with problems
infra/bootstrap: 1 resources checked, 5 without tag support, 0 with problems
OK: every resource follows the tagging policy.
```

*Without tag support* are resource types that AWS does not tag (route table associations, bucket settings,
lifecycle policies, `random_password`...). A resource with a problem prints a `FAIL` line with its address and what is missing.

- `--stack` runs `terraform show -json` and keeps the result in memory: the state contains generated secrets, so it is never written to a file.
- `--aws` uses the Resource Groups Tagging API. It only finds resources that have the `Project` tag; resources with no tags at all are caught by `--stack`.
- Resources created by AWS on our behalf (network interfaces of Fargate tasks and of the ALB, the RDS master secret) are not tagged by us and are not checked.
