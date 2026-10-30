# Centralized logs (US-27, T-27.4)

Every container sends stdout and stderr to **CloudWatch Logs** with the `awslogs` driver (configured in the
task definitions, T-27.2). Terraform: `infra/modules/logs`.

## Log groups

| Log group | Service | What it contains |
|---|---|---|
| `/ecs/voltiagrid-dev/api-customer-consumption` | Customer consumption API | uvicorn start, one access line per request, errors |
| `/ecs/voltiagrid-dev/api-control-center` | Control center API | same, plus calls to F5 that fail (502) |
| `/ecs/voltiagrid-dev/api-network-inventory` | Network inventory API | same |
| `/ecs/voltiagrid-dev/api-transformer-metering` | F5 simulator | same |
| `/ecs/voltiagrid-dev/migrate-seed` | One-off migrations + seed task | Alembic output and seed summary |

- Each task writes to its own **stream** `<service>/<container>/<task id>`.
- **Retention: 7 days.** dev only lives during test windows; logs are deleted automatically afterwards.
- Cost: 0.50 USD per GB ingested and 0.03 USD per GB-month stored. A dev window writes a few MB.

## Follow the logs of a service

```powershell
aws logs tail /ecs/voltiagrid-dev/api-control-center --follow --since 10m
```

Ctrl+C stops it. Without `--follow` it prints and exits.

## Check that a request reaches CloudWatch

1. Call the API through the load balancer (T-27.3), for example its health check:
   ```powershell
   $alb = terraform -chdir=infra/envs/dev output -raw alb_url
   Invoke-RestMethod "$alb/control-center/health"
   ```
2. Within a few seconds the access line appears:
   ```powershell
   aws logs tail /ecs/voltiagrid-dev/api-control-center --since 5m --filter-pattern '"GET /control-center/health"'
   ```
   Expected line: `INFO:     <ip>:<port> - "GET /control-center/health HTTP/1.1" 200 OK`.

## Search across services (Logs Insights)

Console → CloudWatch → **Logs Insights** → select the `/ecs/voltiagrid-dev/` log groups → paste:

```
fields @timestamp, @logStream, @message
| filter @message like /HTTP\/1.1" 5\d\d/
| sort @timestamp desc
| limit 50
```

It lists the requests that ended with a 5xx error in the selected time range. Change the filter to
`/Traceback/` to find unhandled exceptions.

## What is not logged

- Secrets: the containers receive them as environment variables and never print them. Do not add log lines with `os.environ`.
- Load balancer access logs: they need an S3 bucket and are left for the observability story (US-63).
