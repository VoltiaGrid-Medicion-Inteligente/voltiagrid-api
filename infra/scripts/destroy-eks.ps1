<#
.SYNOPSIS
  Destroys the EKS cluster of the comparison window and checks that nothing of it is left (US-50, T-50.4).

.DESCRIPTION
  1. Deletes the namespace voltiagrid (the F5 Deployment, Service, ConfigMap and Secret), so no pod holds a network
     interface while the nodes go away.
  2. Runs terraform destroy on infra/envs/eks (cluster, node group, its subnets, IAM roles and the RDS rule).
  3. Asks AWS directly: no cluster voltiagrid-dev-eks, no EC2 node of it, no network interface left in its subnets.
  The dev stack (infra/envs/dev) is not touched; infra/scripts/destroy.ps1 calls this script first when it finds the
  cluster.

.EXAMPLE
  .\infra\scripts\destroy-eks.ps1 -AutoApprove
#>
param(
    [switch]$AutoApprove,
    [string]$Region = "us-east-1",
    [string]$ClusterName = "voltiagrid-dev-eks"
)

$ErrorActionPreference = "Stop"
$Stack = "infra/envs/eks"
$approve = @()
if ($AutoApprove) { $approve = @("-auto-approve") }

if (-not (Test-Path "infra/scripts/destroy-eks.ps1")) { throw "Run this script from the root of voltiagrid-api." }

$account = (aws sts get-caller-identity --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0 -or -not $account) { throw "No AWS session. Run: aws sso login --profile voltia-admin" }

$exists = aws eks describe-cluster --region $Region --name $ClusterName --query cluster.status --output text 2>$null
if ($LASTEXITCODE -eq 0 -and $exists) {
    Write-Host "Cluster $ClusterName is $exists. Deleting the namespace voltiagrid first ..."
    aws eks update-kubeconfig --region $Region --name $ClusterName | Out-Null
    if ($LASTEXITCODE -eq 0) {
        kubectl delete namespace voltiagrid --ignore-not-found --wait=true --timeout=180s
        if ($LASTEXITCODE -ne 0) { Write-Host "  namespace not deleted (continuing: terraform removes the nodes)" -ForegroundColor Yellow }
    }
} else {
    Write-Host "Cluster $ClusterName not found: running terraform destroy anyway to clean the rest of the stack."
}

$watch = [System.Diagnostics.Stopwatch]::StartNew()
terraform "-chdir=$Stack" init -input=false -reconfigure "-backend-config=bucket=voltiagrid-tfstate-$account" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "terraform init failed" }
terraform "-chdir=$Stack" destroy -input=false @approve
if ($LASTEXITCODE -ne 0) { throw "terraform destroy failed" }
$minutes = [math]::Round($watch.Elapsed.TotalMinutes, 1)

Write-Host ""
Write-Host "===== Anything of the EKS window left in ${Region}?"
$checks = [ordered]@{
    "EKS cluster"                  = @("eks", "list-clusters", "--query", "clusters[?@=='$ClusterName']")
    "EC2 nodes of the cluster"     = @("ec2", "describe-instances", "--filters", "Name=tag:eks:cluster-name,Values=$ClusterName", "Name=instance-state-name,Values=pending,running,stopping,stopped", "--query", "Reservations[].Instances[].InstanceId")
    "Network interfaces (cluster)" = @("ec2", "describe-network-interfaces", "--filters", "Name=tag:cluster.k8s.amazonaws.com/name,Values=$ClusterName", "--query", "NetworkInterfaces[].NetworkInterfaceId")
    "Subnets of the cluster"       = @("ec2", "describe-subnets", "--filters", "Name=tag:Name,Values=$ClusterName-nodes-*", "--query", "Subnets[].SubnetId")
}

$left = 0
foreach ($name in $checks.Keys) {
    $cmd = $checks[$name] + @("--region", $Region, "--output", "json")
    $found = (& aws @cmd | ConvertFrom-Json)
    $count = @($found).Where({ $_ }).Count
    $left += $count
    $mark = "OK  "
    if ($count -gt 0) { $mark = "LEFT" }
    Write-Host ("  [{0}] {1,-30} {2}" -f $mark, $name, ($found -join ", "))
}

Write-Host ""
Write-Host "terraform destroy of EKS took $minutes minutes."
if ($left -gt 0) {
    Write-Host "Something of the cluster is still there: wait a minute and run the script again, or delete it in the console." -ForegroundColor Red
    exit 1
}
Write-Host "Nothing of the EKS window left. The dev stack is untouched."
