# Deploy the services to AWS (US-27)

How a version of the code ends up running on ECS Fargate behind the load balancer.
Everything here runs from the root of `voltiagrid-api` in PowerShell, with Docker Desktop running.

```powershell
aws sso login --profile voltia-admin
$env:AWS_PROFILE = "voltia-admin"
$bucket = terraform -chdir=infra/bootstrap output -raw state_bucket
terraform -chdir=infra/envs/dev init -backend-config="bucket=$bucket"
```

## 1. Images in ECR (T-27.1)

Repositories (created by `infra/modules/ecr`):

| Repository | Dockerfile | Runs as |
|---|---|---|
| `voltiagrid/api-customer-consumption` | `app/api/customer_consumption/Dockerfile` | ECS service, port 8001 |
| `voltiagrid/api-control-center` | `app/api/control_center/Dockerfile` | ECS service, port 8002 |
| `voltiagrid/api-network-inventory` | `app/api/network_inventory/Dockerfile` | ECS service, port 8003 |
| `voltiagrid/api-transformer-metering` | `simulators/transformer_api/Dockerfile` | ECS service, port 8005 (F5) |
| `voltiagrid/migrate-seed` | `seed/Dockerfile` | One-off ECS task: migrations + seed |

- **Tag = short git commit** (`git rev-parse --short HEAD`). Tags are immutable, so a tag always means the same code.
- Every push is scanned for known vulnerabilities (`scan_on_push`).
- ECR keeps the last 10 images per repository.

The repositories must exist before pushing. The first time in a window, create the stack with no running tasks
(`desired_count` exists once the ECS services are added, T-27.2):

```powershell
terraform -chdir=infra/envs/dev apply -var desired_count=0
```

Then build and push every image with the current commit as tag:

```powershell
.\infra\scripts\publish-images.ps1
```

The script refuses to run with uncommitted changes, skips tags already in ECR, and prints the command to deploy that tag.
To publish only one image: `.\infra\scripts\publish-images.ps1 -Only api-control-center`.

Check:

```powershell
aws ecr describe-images --repository-name voltiagrid/api-control-center --query "imageDetails[].{tag:imageTags[0],pushed:imagePushedAt,scan:imageScanStatus.status}" --output table
```

If PowerShell says the script "cannot be loaded because running scripts is disabled", allow local scripts for
your user once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 2. ECS cluster, task definitions and services (T-27.2)

Created by `infra/modules/ecs` (cluster `voltiagrid-dev`):

| Task definition family | Service | Port | Size | Secrets injected |
|---|---|---|---|---|
| `voltiagrid-dev-api-customer-consumption` | yes | 8001 | 0.25 vCPU / 0.5 GB | DB user and password, JWT secret, demo passwords |
| `voltiagrid-dev-api-control-center` | yes | 8002 | 0.25 vCPU / 0.5 GB | DB user and password, JWT secret |
| `voltiagrid-dev-api-network-inventory` | yes | 8003 | 0.25 vCPU / 0.5 GB | DB user and password, JWT secret |
| `voltiagrid-dev-api-transformer-metering` | yes | 8005 | 0.25 vCPU / 0.5 GB | DB user and password |
| `voltiagrid-dev-migrate-seed` | no (one-off task) | — | 0.5 vCPU / 1 GB | DB user and password |

- **Versioned deployment.** The image in every task definition is `<repository>:<image_tag>`. Each apply with a new
  `image_tag` registers a new revision (`...:1`, `...:2`) and the service rolls to it. If the new tasks never become
  healthy, the deployment circuit breaker rolls back to the previous revision.
- **Roles.** The *execution role* pulls from ECR, writes logs and reads only the two secrets. The *task role*
  (what the code may do in AWS) has no permissions: the APIs call no AWS service.
- **Network.** Public subnets with a public IP, Security Group `voltiagrid-dev-app` (inbound only from the ALB).
- Each container has the same health check as its Dockerfile (`GET /health` on its port).

Deploy a tag (after publishing it, section 1):

```powershell
$tag = git rev-parse --short HEAD
terraform -chdir=infra/envs/dev apply -var image_tag=$tag
```

Without `-var image_tag`, an apply with running tasks stops with a clear message: use `-var desired_count=0`
to create everything without tasks.

Check:

```powershell
aws ecs describe-services --cluster voltiagrid-dev `
  --services api-customer-consumption api-control-center api-network-inventory api-transformer-metering `
  --query "services[].{service:serviceName,running:runningCount,desired:desiredCount,taskDef:taskDefinition}" --output table
```

`running` must equal `desired`, and `taskDef` ends with the revision just created.

## 3. Load balancer and health checks (T-27.3)

One internet-facing **Application Load Balancer** in the two public subnets, listener on port 80, one target group
per service and a rule per path prefix (`infra/modules/alb`):

| Path on the ALB | Service | Target group | Health check |
|---|---|---|---|
| `/consumption/*` | api-customer-consumption | `voltiagrid-dev-consumption` | `GET /health` on 8001, `200` |
| `/control-center/*` | api-control-center | `voltiagrid-dev-control-center` | `GET /health` on 8002, `200` |
| `/inventory/*` | api-network-inventory | `voltiagrid-dev-inventory` | `GET /health` on 8003, `200` |
| `/f5/*` | api-transformer-metering | `voltiagrid-dev-f5` | `GET /health` on 8005, `200` |
| anything else | — | — | JSON `404` from the listener |

- The ALB does not remove the prefix. Each API runs with `ROOT_PATH=<prefix>` and answers both `<prefix>/health`
  (through the ALB) and `/health` (container and target group health checks). Swagger works at `<prefix>/docs`.
- The control center calls F5 through the ALB: `F5_URL=http://<alb>/f5`.
- Health check every 15 s; a target is healthy after 2 good checks and removed after 3 bad ones.
- HTTP only: the pilot has no domain name for a TLS certificate.

Check (after section 2 with running tasks):

```powershell
$alb = terraform -chdir=infra/envs/dev output -raw alb_url
Invoke-RestMethod "$alb/consumption/health"
Invoke-RestMethod "$alb/control-center/health"
Invoke-RestMethod "$alb/inventory/health"
Invoke-RestMethod "$alb/f5/health"
foreach ($tg in "consumption","control-center","inventory","f5") {
  $arn = aws elbv2 describe-target-groups --names "voltiagrid-dev-$tg" --query "TargetGroups[0].TargetGroupArn" --output text
  aws elbv2 describe-target-health --target-group-arn $arn --query "TargetHealthDescriptions[].TargetHealth.State" --output text
}
```

Each `health` answers `status: ok`, and each target group prints `healthy`. Open `$alb/consumption/docs` in the browser
to try the API, or use the Bruno environment `aws` (replace `REPLACE-WITH-ALB-DNS` with the DNS name of `$alb`).

## 4. Database and full deployment window (T-25.3)

The order of a full window, from nothing to the APIs answering through the ALB with RDS data:

```powershell
# 0. Session and state
aws sso login --profile voltia-admin
$env:AWS_PROFILE = "voltia-admin"
$bucket = terraform -chdir=infra/bootstrap output -raw state_bucket
terraform -chdir=infra/envs/dev init -backend-config="bucket=$bucket"

# 1. Infrastructure without running tasks (network, RDS, secrets, ECR, logs, ALB, ECS definitions): 10-15 min
terraform -chdir=infra/envs/dev apply -var desired_count=0

# 2. Images of the current commit
.\infra\scripts\publish-images.ps1
$tag = git rev-parse --short HEAD

# 3. Task definitions with that tag, still no tasks; then migrations and seed in RDS
terraform -chdir=infra/envs/dev apply -var image_tag=$tag -var desired_count=0
.\infra\scripts\run-task.ps1 -Job migrate-seed
.\infra\scripts\run-task.ps1 -Job hashes

# 4. Start the services: 1 task each
terraform -chdir=infra/envs/dev apply -var image_tag=$tag

# 5. Check (sections 2 and 3), test with Bruno, look at the logs (LOGS.md)

# 6. End of the window: destroy everything in dev
terraform -chdir=infra/envs/dev destroy -var image_tag=$tag
```

Details of the database steps and the comparison with local data: `RDS.md`.
