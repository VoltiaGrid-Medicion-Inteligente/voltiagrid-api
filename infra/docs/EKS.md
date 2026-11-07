# EKS for the ECS vs EKS comparison (US-50)

ADR-014: the F5 transformer metering simulator runs on EKS in weeks 5 and 6 to compare it with ECS; the rest of the
time it runs on ECS. The cluster exists only during a test window, like the dev stack, and is destroyed at the end.

## 1. The cluster (T-50.1)

`infra/envs/eks` is its own stack (state key `eks/terraform.tfstate`), created **after** `infra/envs/dev` and
destroyed **before** it:

| Resource | Why |
|---|---|
| EKS cluster `voltiagrid-dev-eks` (Kubernetes 1.33) | Control plane managed by AWS; API reachable from the laptops (public endpoint) and from the nodes inside the VPC (private endpoint) |
| Managed node group `default`: 1 × `t3.small`, on-demand (max 2) | Enough for the F5 pod and the system pods (11 pods fit a t3.small) |
| 2 public subnets `10.20.20.0/24` and `10.20.21.0/24` in the dev VPC | The nodes need a public IP to pull images and join the cluster (no NAT, ADR-011); the dev subnets do not give one on launch and stay as they are |
| IAM roles for the cluster and the nodes | AWS managed policies; the nodes may pull from ECR |
| Rule on the dev RDS security group: 5432 from the cluster security group | The F5 pod reads F4 from the same RDS as on ECS |
| Access entry for whoever creates it (`authentication_mode = API`) | That person is cluster admin; no `aws-auth` ConfigMap |

```powershell
aws sso login --profile voltia-admin
$env:AWS_PROFILE = "voltia-admin"
$bucket = terraform -chdir=infra/bootstrap output -raw state_bucket
terraform -chdir=infra/envs/eks init -backend-config="bucket=$bucket"
terraform -chdir=infra/envs/eks apply                     # about 12-15 minutes: the control plane takes the longest
Invoke-Expression (terraform -chdir=infra/envs/eks output -raw kubeconfig_command)
kubectl get nodes                                         # one node, STATUS Ready
```

Cost while it exists: control plane 0.10 USD/hour + t3.small 0.0208 USD/hour + its 20 GB disk, about 0.12 USD per
hour of window. Check `aws eks describe-cluster-versions --region us-east-1` before a window: if 1.33 left standard
support, pass `-var kubernetes_version=<newer>` (extended support costs 0.60 USD/hour).

## 2. The F5 simulator on the cluster (T-50.2)

`k8s/f5/` has the three objects US-50 asks for, with the same image, port, size, health check and variables as the
ECS task of `api-transformer-metering`, so the comparison is only about the orchestrator:

| File | Object | What it does |
|---|---|---|
| `namespace.yaml` | Namespace `voltiagrid` | Groups the project's objects; deleting it deletes them all |
| `deployment.yaml` | Deployment `f5` | 1 replica, 0.25 vCPU / 512 MB, non-root user 10001, readiness and liveness probes on `/health`; database host from the ConfigMap `f5-db`, user and password from the Secret `f5-db` |
| `service.yaml` | Service `f5` (ClusterIP, port 8005) | Stable address `http://f5.voltiagrid:8005` inside the cluster; no load balancer (not needed for the comparison, it would cost more) |

The image tag and the secrets are not in git. `infra/scripts/eks-deploy-f5.ps1` sets them during the window:

```powershell
.\infra\scripts\eks-deploy-f5.ps1 -Tag <short commit published to ECR>
```

It creates the ConfigMap with the RDS host of the dev stack and the Secret with the user and password of the RDS
secret in Secrets Manager, applies the manifests with `voltiagrid/api-transformer-metering:<Tag>`, waits for the
rollout and calls the API through a port-forward:

```
deployment.apps/f5   1/1   ...
pod/f5-6c9f...       1/1   Running
service/f5           ClusterIP   172.20.x.x   8005/TCP
  /health -> ok
  /transformers -> <number of transformers of the seed> transformers
```

Evidence for US-50: that output, `kubectl get all -n voltiagrid` and `kubectl describe deployment f5 -n voltiagrid`.
