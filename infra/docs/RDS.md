# Operational database on RDS (US-25)

Terraform: `infra/modules/rds`, used by `infra/envs/dev`.

## Configuration (T-25.1)

| Setting         | Value                                                                       | Why                                                                                          |
| --------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Engine          | PostgreSQL 16                                                               | Same major version as `docker-compose.yml` (`postgres:16`)                                   |
| Instance        | `db.t4g.micro` (2 vCPU burstable, 1 GB)                                     | Cheapest Graviton class; enough for the dev windows (docs: Costs)                            |
| Storage         | 20 GB gp3, encrypted (AWS managed key)                                      | Minimum size; encryption at rest has no extra cost                                           |
| Network         | DB subnet group with the two private subnets, `publicly_accessible = false` | Never reachable from the internet                                                            |
| Security Group  | 5432 only from the app tasks and the admin instance                         | T-21.2                                                                                       |
| SSL             | Parameter `rds.force_ssl = 1`                                               | The server refuses connections without SSL                                                   |
| Master password | `manage_master_user_password = true`                                        | RDS creates it and keeps it in Secrets Manager; it is not in the code, the plan or the state |
| Backups         | Automatic, every day at 06:00 UTC, kept **7 days**, point-in-time restore   | Requirement of US-25                                                                         |
| Maintenance     | Sundays 07:30 UTC, minor versions applied automatically                     | Security patches without manual work                                                         |
| Availability    | Single-AZ                                                                   | Pilot; Multi-AZ doubles the price (docs: Alternatives)                                       |
| Destroy in dev  | No final snapshot, no deletion protection                                   | dev is rebuilt by the seed in every window                                                   |

## Private: a connection from the internet is rejected

After an apply, from your laptop:

```powershell
$db = terraform -chdir=infra/envs/dev output -raw rds_address
Resolve-DnsName $db | Select-Object -ExpandProperty IPAddress
Test-NetConnection $db -Port 5432
```

- `Resolve-DnsName` returns a **private** address (`10.20.10.x` or `10.20.11.x`), which is not routable from the internet.
- `Test-NetConnection` ends with `TcpTestSucceeded : False`.
- `aws rds describe-db-instances --db-instance-identifier voltiagrid-dev-db --query "DBInstances[0].PubliclyAccessible"` returns `false`.

To reach it, use the admin instance tunnel (docs: Infrastructure → Admin instance).

## Backups

```powershell
aws rds describe-db-instances --db-instance-identifier voltiagrid-dev-db `
  --query "DBInstances[0].{retention:BackupRetentionPeriod,window:PreferredBackupWindow,latestRestorable:LatestRestorableTime}"
```

`retention` must be `7`. `latestRestorable` appears a few minutes after the instance is created.

## Credentials

```powershell
$arn = terraform -chdir=infra/envs/dev output -raw rds_master_secret_arn
aws secretsmanager describe-secret --secret-id $arn --query "{name:Name,rotation:RotationEnabled}"
```

The secret is a JSON with `username` and `password`. Do not print the value in a shared screen or paste it anywhere.
RDS rotates it every 7 days; a dev window lasts a few hours, so tasks started in the window keep working.
