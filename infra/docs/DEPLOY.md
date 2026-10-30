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
