<#
.SYNOPSIS
  Puts an ECS service back on an earlier task definition revision, the version that worked (US-46, T-46.3).

.DESCRIPTION
  Every deployment (the pipeline or terraform apply) registers a new revision of the service's task definition; the
  old ones stay registered. Rolling back is pointing the service at one of them again:
    1. finds the revision the service runs now;
    2. without -Revision, takes the previous ACTIVE revision of the same family;
    3. updates the service and waits until it is stable (ECS replaces the tasks one by one: no downtime);
    4. prints the image of both revisions and the health of the API through the ALB.
  -All rolls back the four API services, each to its previous revision.

.EXAMPLE
  .\infra\scripts\rollback.ps1 -Service api-control-center
  .\infra\scripts\rollback.ps1 -Service api-control-center -Revision 7
  .\infra\scripts\rollback.ps1 -All
#>
param(
    [ValidateSet("api-customer-consumption", "api-control-center", "api-network-inventory", "api-transformer-metering")]
    [string]$Service,
    [int]$Revision = 0,
    [switch]$All,
    [string]$Cluster = "voltiagrid-dev",
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"
$Prefixes = @{
    "api-customer-consumption" = "consumption"; "api-control-center" = "control-center"
    "api-network-inventory" = "inventory"; "api-transformer-metering" = "f5"
}

function Image-Of([string]$TaskDefinition) {
    return (aws ecs describe-task-definition --region $Region --task-definition $TaskDefinition `
            --query "taskDefinition.containerDefinitions[0].image" --output text).Trim()
}

function Roll-Back([string]$Name, [int]$Target) {
    $current = (aws ecs describe-services --region $Region --cluster $Cluster --services $Name `
                --query "services[0].taskDefinition" --output text).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $current -or $current -eq "None") { throw "Service $Name not found in $Cluster" }
    $family = ($current.Split("/")[-1]).Split(":")[0]
    $currentRevision = [int]($current.Split(":")[-1])

    if ($Target -eq 0) {
        $arns = aws ecs list-task-definitions --region $Region --family-prefix $family --status ACTIVE --sort DESC `
                --query "taskDefinitionArns" --output json | ConvertFrom-Json
        $older = $arns | Where-Object { [int]($_.Split(":")[-1]) -lt $currentRevision } | Select-Object -First 1
        if (-not $older) { throw "$Name has no ACTIVE revision older than $currentRevision to go back to" }
        $Target = [int]($older.Split(":")[-1])
    }
    $targetTd = "${family}:$Target"

    Write-Host ""
    Write-Host "===== $Name"
    Write-Host "  now:  ${family}:$currentRevision  $(Image-Of $current)"
    Write-Host "  back: $targetTd  $(Image-Of $targetTd)"
    aws ecs update-service --region $Region --cluster $Cluster --service $Name --task-definition $targetTd `
        --query "service.deployments[0].status" --output text | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "update-service failed for $Name" }
    Write-Host "  waiting until the service is stable ..."
    aws ecs wait services-stable --region $Region --cluster $Cluster --services $Name
    if ($LASTEXITCODE -ne 0) { throw "$Name did not become stable on $targetTd" }
    $running = (aws ecs describe-services --region $Region --cluster $Cluster --services $Name `
                --query "services[0].taskDefinition" --output text).Trim()
    Write-Host "  running: $($running.Split('/')[-1])"
}

if (-not $All -and -not $Service) { throw "Give -Service <name> or -All" }
$services = if ($All) { @($Prefixes.Keys | Sort-Object) } else { @($Service) }
foreach ($name in $services) { Roll-Back $name $(if ($All) { 0 } else { $Revision }) }

$alb = (terraform -chdir=infra/envs/dev output -raw alb_url 2>$null)
if ($alb) {
    Write-Host ""
    foreach ($name in $services) {
        $url = "$($alb.Trim())/$($Prefixes[$name])/health"
        try { Write-Host "  $url -> $((Invoke-RestMethod -Uri $url -TimeoutSec 10).status)" }
        catch { Write-Host "  $url -> no answer yet: $($_.Exception.Message)" }
    }
}
Write-Host ""
Write-Host "Next terraform apply of this window: pass the image tag of the revision you went back to (-var image_tag=...)."
