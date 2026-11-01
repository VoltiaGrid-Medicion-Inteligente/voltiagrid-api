<#
.SYNOPSIS
  Creates the whole dev environment from nothing and leaves the APIs answering through the ALB (US-28, T-28.2).

.DESCRIPTION
  Same steps as infra/docs/DEPLOY.md section 4, in one command and with the time of each step:
    1. terraform init with the state bucket of this account
    2. infrastructure without running tasks (desired_count = 0)
    3. images of the current commit to ECR
    4. task definitions with that tag; migrations and seed in RDS (one-off task)
    5. services with 1 task each, wait until they are stable
    6. health of the four APIs through the ALB, and the tag check
  Run it from the root of voltiagrid-api with Docker Desktop running and an admin AWS session.

.EXAMPLE
  aws sso login --profile voltia-admin
  $env:AWS_PROFILE = "voltia-admin"
  .\infra\scripts\deploy.ps1 -AutoApprove
#>
param(
    [switch]$AutoApprove,
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"
$Stack = "infra/envs/dev"
$approve = @()
if ($AutoApprove) { $approve = @("-auto-approve") }

$timings = [ordered]@{}
$total = [System.Diagnostics.Stopwatch]::StartNew()

function Step([string]$Name, [scriptblock]$Body) {
    Write-Host ""
    Write-Host "===== $Name"
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    & $Body
    if ($LASTEXITCODE -ne 0) { throw "$Name failed (exit code $LASTEXITCODE)" }
    $timings[$Name] = [math]::Round($watch.Elapsed.TotalMinutes, 1)
}

if (-not (Test-Path "infra/scripts/deploy.ps1")) { throw "Run this script from the root of voltiagrid-api." }

$account = (aws sts get-caller-identity --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0 -or -not $account) { throw "No AWS session. Run: aws sso login --profile voltia-admin" }
$bucket = "voltiagrid-tfstate-$account"   # created by infra/bootstrap (ADR-012)

Step "1. terraform init" {
    terraform "-chdir=$Stack" init -input=false -reconfigure "-backend-config=bucket=$bucket"
}

Step "2. infrastructure, no tasks" {
    terraform "-chdir=$Stack" apply -input=false @approve -var desired_count=0
}

Step "3. images to ECR" {
    & .\infra\scripts\publish-images.ps1 -Region $Region
}
$tag = (git rev-parse --short HEAD).Trim()

Step "4a. task definitions with tag $tag" {
    terraform "-chdir=$Stack" apply -input=false @approve -var "image_tag=$tag" -var desired_count=0
}

Step "4b. migrations and seed in RDS" {
    & .\infra\scripts\run-task.ps1 -Job migrate-seed
}

Step "5. services running" {
    terraform "-chdir=$Stack" apply -input=false @approve -var "image_tag=$tag" -var desired_count=1
    if ($LASTEXITCODE -ne 0) { return }
    $cluster = (terraform "-chdir=$Stack" output -raw ecs_cluster).Trim()
    aws ecs wait services-stable --region $Region --cluster $cluster `
        --services api-customer-consumption api-control-center api-network-inventory api-transformer-metering
}

Step "6. health through the ALB and tags" {
    $alb = (terraform "-chdir=$Stack" output -raw alb_url).Trim()
    foreach ($prefix in "consumption", "control-center", "inventory", "f5") {
        $ok = $false
        for ($try = 1; $try -le 20 -and -not $ok; $try++) {
            try {
                $answer = Invoke-RestMethod -Uri "$alb/$prefix/health" -TimeoutSec 5
                $ok = ($answer.status -eq "ok")
            } catch { Start-Sleep -Seconds 6 }
        }
        if (-not $ok) { throw "$alb/$prefix/health did not answer ok" }
        Write-Host "  $alb/$prefix/health -> ok"
    }
    python -m scripts.check_tags --stack $Stack --aws --region $Region
}

Write-Host ""
Write-Host "===== Times (minutes)"
foreach ($k in $timings.Keys) { Write-Host ("  {0,-40} {1,5}" -f $k, $timings[$k]) }
Write-Host ("  {0,-40} {1,5}" -f "TOTAL", [math]::Round($total.Elapsed.TotalMinutes, 1))
Write-Host ""
Write-Host "APIs: $((terraform "-chdir=$Stack" output -raw alb_url).Trim())/consumption/docs (and /control-center, /inventory, /f5)"
Write-Host "End of the window: .\infra\scripts\destroy.ps1"
