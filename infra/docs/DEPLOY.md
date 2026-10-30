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
