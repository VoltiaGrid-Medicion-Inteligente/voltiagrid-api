# IaC review of the network

- **Date:** 2026-10-26
- **Reviewers (pair programming):** Sharon Meriño (driver), Carlos Muñoz (author)
- **Commit reviewed:** `9d6defe` Merge pull request #57 (KAN-207) (`git log --oneline -1`)
- **Terraform version:** Terraform v1.16.6

## 1. Code review

| # | Check | Where | Result |
|---|---|---|---|
| 1 | VPC `10.20.0.0/16` with DNS support and hostnames | `modules/network` | OK: `cidr_block = var.cidr`, `vpc_cidr` default `10.20.0.0/16`, DNS support and hostnames `true` |
| 2 | One public and one private subnet in each of `us-east-1a` and `us-east-1b` | `modules/network`, `envs/dev/main.tf` | OK: public `10.20.0.0/24`, `10.20.1.0/24`; private `10.20.10.0/24`, `10.20.11.0/24` |
| 3 | Public subnets do not assign public IPs by default | `map_public_ip_on_launch = false` | OK |
| 4 | Private route table has no `0.0.0.0/0` route when `enable_nat_gateway = false` | `modules/network` | OK: `private_nat` route has `count = var.enable_nat_gateway ? 1 : 0`, default `false` |
| 5 | The default Security Group of the VPC has no rules | `aws_default_security_group` | OK: only `vpc_id` and tags |
| 6 | Only the ALB group accepts traffic from `0.0.0.0/0`, and only on port 80 | `modules/security` | OK: `alb_http` is the only ingress rule with `cidr_ipv4` |
| 7 | App, RDS and endpoint groups only accept traffic from other groups, never from a CIDR | `modules/security` | OK: every other ingress rule uses `referenced_security_group_id` |
| 8 | S3 gateway endpoint attached to the public and the private route tables | `modules/network` | OK |
| 9 | Admin instance: private subnet, no public IP, no key pair, IMDSv2 required, encrypted disk | `modules/admin_instance` | OK |
| 10 | Admin instance role only has `AmazonSSMManagedInstanceCore` | `modules/admin_instance` | OK |
| 11 | Every resource gets `Project`, `Environment`, `Owner`, `ManagedBy` (provider) and `Component` (module) | `envs/dev/providers.tf`, module calls | OK |
| 12 | No secret, account id or IP of a person in the code | whole `infra/` | OK: the account id is resolved at run time, never written |
| 13 | `terraform fmt -check -recursive infra` and `terraform validate` pass | CI job `terraform` | OK: green on PR #57 |

## 2. Apply in AWS

| # | Check | Command | Expected | Result |
|---|---|---|---|---|
| 1 | Plan creates only network, groups, endpoints and the admin instance | `terraform plan` | `Plan: 45 to add, 0 to change, 0 to destroy`; no `aws_nat_gateway` | OK: 45 to add, no NAT Gateway; `Apply complete! Resources: 45 added` |
| 2 | Four subnets in two AZs | `aws ec2 describe-subnets` | 2 public + 2 private, `us-east-1a` and `us-east-1b` | OK: public-a `10.20.0.0/24`, private-a `10.20.10.0/24` (us-east-1a); public-b `10.20.1.0/24`, private-b `10.20.11.0/24` (us-east-1b) |
| 3 | Private route table | `aws ec2 describe-route-tables` | Only `local` and the `pl-...` route to `vpce-...` | OK: `local` and `pl-63a5400a` to `vpce-0e383467548f491ef` |
| 4 | Public route table | `aws ec2 describe-route-tables` | `local`, `0.0.0.0/0` to `igw-...`, `pl-...` to `vpce-...` | OK: local, 0.0.0.0/0 to igw-085755c4dffac2ced, pl-63a5400a to vpce-0e383467548f491ef |
| 5 | Admin instance has no public IP | `aws ec2 describe-instances` | `PublicIpAddress` empty | OK: PublicIpAddress null, IMDSv2 required, private subnet subnet-067c185dca4d9f8ec |
| 6 | Session Manager works without SSH | `aws ssm start-session --target <id>` | A shell `sh-5.2$` opens | OK: session opened, `sh-5.2$` |
| 7 | S3 is reachable from the private subnet | inside the session: `curl -sS -o /dev/null -w "%{http_code}\n" https://s3.us-east-1.amazonaws.com` | An HTTP code (for example `403`) in less than a second | OK: `307` (S3 redirect), immediate |
| 8 | The internet is not reachable from the private subnet | inside the session: `curl -sS -m 5 https://www.google.com` | `Connection timed out` after 5 seconds | OK: `curl: (28) Connection timed out after 5001 milliseconds` |
| 9 | Everything is tagged | `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=voltiagrid` | Every resource lists `Project`, `Environment`, `Owner`, `ManagedBy`, `Component` | OK: 41 resources listed, all with `Component` (`network`, `security-groups`, `admin-instance`, plus `terraform-state` for the state bucket) |

Checks 7 and 8 together prove that S3 traffic leaves through the gateway endpoint: the subnet has no
route to the internet, yet S3 answers.

## 3. Destroy and recreate

| # | Step | Expected | Result |
|---|---|---|---|
| 1 | `terraform destroy` | `Destroy complete!` with the same number of resources created | OK: Destroy complete! Resources: 45 destroyed |
| 2 | `terraform apply` again | `Apply complete!` with the same number of resources | OK: Apply complete! Resources: 45 added |
| 3 | `terraform plan` right after | `No changes. Your infrastructure matches the configuration.` | OK: No changes. Your infrastructure matches the configuration |
| 4 | Final `terraform destroy` | `Destroy complete!`; nothing left running | OK: Destroy complete! Resources: 45 destroyed (about 4 min); terraform state list is empty |

Time of the whole window: 37 minutes. The `terraform apply` and `terraform destroy` outputs are pasted in the pull request.

## Findings

- S3 answered `307` (a redirect, because no bucket was requested) instead of the `403` used as an example. Any HTTP code proves that S3 is reachable from the private subnet.
- The tagging API lists 41 of the 45 resources: routes, route table associations and the IAM policy attachment do not support tags. Every taggable resource has `Component`.
- The first `apply` of `infra/bootstrap` failed with `No valid credential sources found` because the SSO session had expired. Fixed with `aws sso login --profile voltia-admin` and `$env:AWS_PROFILE = "voltia-admin"`.
- AWS CLI paginated long outputs (`-- More --`). Setting `$env:AWS_PAGER = ""` turns it off for the session.
- The local state of `infra/bootstrap` (`terraform.tfstate`) is not in Git; a copy was saved outside the repository.