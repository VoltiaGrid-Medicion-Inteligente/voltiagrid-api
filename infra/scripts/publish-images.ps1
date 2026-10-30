<#
.SYNOPSIS
  Builds the images of the services deployed on ECS and pushes them to ECR (US-27, T-27.1).

.DESCRIPTION
  The tag is the short git commit (for example 3f2a1c9), so every image in ECR can be traced to its code.
  Repositories have immutable tags: if a tag is already in ECR it is skipped, not overwritten.
  Run it from the root of voltiagrid-api, with Docker Desktop running and an AWS profile signed in.

.EXAMPLE
  aws sso login --profile voltia-admin
  $env:AWS_PROFILE = "voltia-admin"
  .\infra\scripts\publish-images.ps1
  .\infra\scripts\publish-images.ps1 -Only api-control-center
#>
param(
    [string]$Tag = "",
    [string]$Region = "us-east-1",
    [string[]]$Only = @()
)

$ErrorActionPreference = "Stop"

# Image name -> Dockerfile (same as docker-compose.yml)
$Images = [ordered]@{
    "api-customer-consumption" = "app/api/customer_consumption/Dockerfile"
    "api-control-center"       = "app/api/control_center/Dockerfile"
    "api-network-inventory"    = "app/api/network_inventory/Dockerfile"
    "api-transformer-metering" = "simulators/transformer_api/Dockerfile"
    "migrate-seed"             = "seed/Dockerfile"
}

function Invoke-Native {
    # Runs a command and stops the script if it fails (works in Windows PowerShell 5.1 and PowerShell 7).
    param([string]$What, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)" }
}

if (-not (Test-Path "infra/scripts/publish-images.ps1")) {
    throw "Run this script from the root of the voltiagrid-api repository."
}

if (-not $Tag) {
    $Tag = (git rev-parse --short HEAD).Trim()
    $dirty = git status --porcelain --untracked-files=no
    if ($dirty) {
        throw "There are uncommitted changes. Commit them first: the image tag must match a commit."
    }
}

Invoke-Native "docker info" { docker info --format "{{.ServerVersion}}" | Out-Null }
$account = (aws sts get-caller-identity --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0 -or -not $account) { throw "No AWS session. Run: aws sso login --profile voltia-admin" }
$registry = "$account.dkr.ecr.$Region.amazonaws.com"

Write-Host "Registry: $registry   Tag: $Tag"
Invoke-Native "docker login to ECR" {
    aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $registry
}

$names = @($Images.Keys)
if ($Only.Count -gt 0) { $names = @($names | Where-Object { $Only -contains $_ }) }

foreach ($name in $names) {
    $repo = "voltiagrid/$name"
    $remote = "$registry/${repo}:$Tag"

    # "Continue" here: in Windows PowerShell 5.1 a redirected error of a native command would stop the script.
    $ErrorActionPreference = "Continue"
    $existing = aws ecr describe-images --region $Region --repository-name $repo --image-ids "imageTag=$Tag" --query "imageDetails[0].imageTags" --output text 2>$null
    $found = ($LASTEXITCODE -eq 0 -and $existing)
    $ErrorActionPreference = "Stop"
    if ($found) {
        Write-Host "== $name : $Tag already in ECR, skipped"
        continue
    }

    Write-Host "== $name : build"
    Invoke-Native "docker build $name" { docker build --platform linux/amd64 -f $Images[$name] -t "${repo}:local" -t $remote . }
    Write-Host "== $name : push"
    Invoke-Native "docker push $name" { docker push $remote }
}

Write-Host ""
Write-Host "Done. Deploy this version with:"
Write-Host "  terraform -chdir=infra/envs/dev apply -var image_tag=$Tag"
