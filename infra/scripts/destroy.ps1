<#
.SYNOPSIS
  Destroys the dev environment and checks that nothing billable is left (US-28, T-28.2).

.DESCRIPTION
  Runs terraform destroy on infra/envs/dev, then asks AWS directly for anything that costs per hour:
  EC2 instances, RDS instances, load balancers, NAT Gateways, Elastic IPs, interface endpoints and ECS tasks.
  The data lake (infra/envs/data) and the state bucket are NOT touched: they are persistent (ADR-012).
  If the EKS cluster of the comparison window exists (US-50), infra/scripts/destroy-eks.ps1 runs first: the cluster
  uses subnets of the dev VPC and a rule on the RDS security group, so dev cannot be destroyed while it is there.

.EXAMPLE
  .\infra\scripts\destroy.ps1 -AutoApprove
#>
param(
    [switch]$AutoApprove,
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"
$Stack = "infra/envs/dev"
$approve = @()
if ($AutoApprove) { $approve = @("-auto-approve") }

if (-not (Test-Path "infra/scripts/destroy.ps1")) { throw "Run this script from the root of voltiagrid-api." }

$account = (aws sts get-caller-identity --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0 -or -not $account) { throw "No AWS session. Run: aws sso login --profile voltia-admin" }

$eks = aws eks list-clusters --region $Region --query "clusters[?@=='voltiagrid-dev-eks']" --output text
if ($eks) {
    Write-Host "The EKS cluster of US-50 exists: destroying it first (infra/scripts/destroy-eks.ps1) ..."
    & "$PSScriptRoot/destroy-eks.ps1" -AutoApprove:$AutoApprove -Region $Region
    if ($LASTEXITCODE -ne 0) { throw "destroy-eks.ps1 failed: dev is not destroyed while the cluster uses its VPC" }
}

$watch = [System.Diagnostics.Stopwatch]::StartNew()
terraform "-chdir=$Stack" init -input=false -reconfigure "-backend-config=bucket=voltiagrid-tfstate-$account" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "terraform init failed" }

# image_tag is irrelevant for a destroy; passing it avoids the precondition of the services.
terraform "-chdir=$Stack" destroy -input=false @approve -var image_tag=destroy -var desired_count=0
if ($LASTEXITCODE -ne 0) { throw "terraform destroy failed" }
$minutes = [math]::Round($watch.Elapsed.TotalMinutes, 1)

Write-Host ""
Write-Host "===== Anything billable left in ${Region}?"
$checks = [ordered]@{
    "EC2 instances (running or stopped)" = @("ec2", "describe-instances", "--filters", "Name=tag:Project,Values=voltiagrid", "Name=instance-state-name,Values=pending,running,stopping,stopped", "--query", "Reservations[].Instances[].InstanceId")
    "RDS instances"                      = @("rds", "describe-db-instances", "--query", "DBInstances[?starts_with(DBInstanceIdentifier, 'voltiagrid-')].DBInstanceIdentifier")
    "Load balancers"                     = @("elbv2", "describe-load-balancers", "--query", "LoadBalancers[?starts_with(LoadBalancerName, 'voltiagrid-')].LoadBalancerName")
    "NAT Gateways"                       = @("ec2", "describe-nat-gateways", "--filter", "Name=tag:Project,Values=voltiagrid", "Name=state,Values=pending,available", "--query", "NatGateways[].NatGatewayId")
    "Elastic IPs"                        = @("ec2", "describe-addresses", "--filters", "Name=tag:Project,Values=voltiagrid", "--query", "Addresses[].PublicIp")
    "VPC endpoints"                      = @("ec2", "describe-vpc-endpoints", "--filters", "Name=tag:Project,Values=voltiagrid", "--query", "VpcEndpoints[?State!='deleted'].VpcEndpointId")
    "ECS clusters"                       = @("ecs", "describe-clusters", "--clusters", "voltiagrid-dev", "--query", "clusters[?status=='ACTIVE'].clusterName")
}

$left = 0
foreach ($name in $checks.Keys) {
    $cmd = $checks[$name] + @("--region", $Region, "--output", "json")
    $found = (& aws @cmd | ConvertFrom-Json)
    $count = @($found).Where({ $_ }).Count
    $left += $count
    $mark = "OK  "
    if ($count -gt 0) { $mark = "LEFT" }
    Write-Host ("  [{0}] {1,-36} {2}" -f $mark, $name, ($found -join ", "))
}

Write-Host ""
Write-Host "terraform destroy took $minutes minutes."
if ($left -gt 0) {
    Write-Host "Something is still running: delete it (console or terraform) before leaving." -ForegroundColor Red
    exit 1
}
Write-Host "Nothing billable left in dev. The data lake and the state bucket are kept on purpose."
