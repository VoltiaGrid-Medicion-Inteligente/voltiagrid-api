<#
.SYNOPSIS
  Deploys the F5 simulator to the EKS cluster of the window and checks it answers (US-50, T-50.2).

.DESCRIPTION
  1. Points kubectl at voltiagrid-dev-eks (infra/envs/eks applied).
  2. Creates the namespace, the ConfigMap f5-db (RDS host, port, database) and the Secret f5-db (user and password
     read from the RDS secret in Secrets Manager; nothing secret on disk or in git).
  3. Applies k8s/f5 with the image voltiagrid/api-transformer-metering:<Tag> of ECR (it replaces the placeholder
     image of deployment.yaml) and waits for the rollout.
  4. Port-forwards the Service and calls /health and /transformers.

.EXAMPLE
  .\infra\scripts\eks-deploy-f5.ps1 -Tag 3f2a1c9
#>
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

function Invoke-Native([string]$What, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)" }
}

$cluster = (terraform -chdir=infra/envs/eks output -raw cluster_name).Trim()
$rdsHost = (terraform -chdir=infra/envs/dev output -raw rds_address).Trim()
$secretArn = (terraform -chdir=infra/envs/dev output -raw rds_master_secret_arn).Trim()
$account = (aws sts get-caller-identity --query Account --output text).Trim()
$image = "$account.dkr.ecr.$Region.amazonaws.com/voltiagrid/api-transformer-metering:$Tag"

Invoke-Native "update-kubeconfig" { aws eks update-kubeconfig --region $Region --name $cluster | Out-Null }
Invoke-Native "namespace" { kubectl apply -f k8s/f5/namespace.yaml }

# ConfigMap and Secret through --dry-run | apply, so running the script twice updates them instead of failing.
$credentials = aws secretsmanager get-secret-value --region $Region --secret-id $secretArn --query SecretString --output text | ConvertFrom-Json
Invoke-Native "configmap f5-db" {
    kubectl create configmap f5-db -n voltiagrid --from-literal=DB_HOST=$rdsHost --from-literal=DB_PORT=5432 `
        --from-literal=DB_NAME=voltiagrid --dry-run=client -o yaml | kubectl apply -f -
}
Invoke-Native "secret f5-db" {
    kubectl create secret generic f5-db -n voltiagrid --from-literal=DB_USER=$($credentials.username) `
        --from-literal=DB_PASSWORD=$($credentials.password) --dry-run=client -o yaml | kubectl apply -f -
}
$credentials = $null

# The manifest names a placeholder image; it is replaced with the ECR image of this account and tag before applying.
$placeholder = "ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/voltiagrid/api-transformer-metering:TAG"
Invoke-Native "deployment ($image)" {
    (Get-Content k8s/f5/deployment.yaml -Raw).Replace($placeholder, $image) | kubectl apply -f -
}
Invoke-Native "service" { kubectl apply -f k8s/f5/service.yaml }
Invoke-Native "rollout" { kubectl rollout status deployment/f5 -n voltiagrid --timeout=180s }
kubectl get deployment,pods,service -n voltiagrid -o wide

Write-Host ""
Write-Host "Checking through a port-forward to the Service ..."
$forward = Start-Process kubectl -ArgumentList "port-forward", "service/f5", "-n", "voltiagrid", "18005:8005" -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 4
    Write-Host "  /health -> $((Invoke-RestMethod -Uri http://localhost:18005/health -TimeoutSec 10).status)"
    $transformers = Invoke-RestMethod -Uri http://localhost:18005/transformers -TimeoutSec 20
    Write-Host "  /transformers -> $(@($transformers).Count) transformers"
}
finally {
    Stop-Process -Id $forward.Id -ErrorAction SilentlyContinue
}
