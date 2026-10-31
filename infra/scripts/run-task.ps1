<#
.SYNOPSIS
  Runs a one-off ECS task with the migrate-seed image inside the VPC and prints its log (US-25, T-25.3).

.DESCRIPTION
  -Job migrate-seed  runs "alembic upgrade head" and the seed against RDS (same command as docker-compose).
  -Job hashes        runs "python -m seed.hashes": row count and md5 of every F4 table, to compare with local.
  The task uses the public subnets and the app Security Group, reads the RDS credentials from Secrets Manager
  and connects with SSL. The script waits until the task stops and exits with the container's exit code.

.EXAMPLE
  .\infra\scripts\run-task.ps1 -Job migrate-seed
  .\infra\scripts\run-task.ps1 -Job hashes
#>
param(
    [ValidateSet("migrate-seed", "hashes")]
    [string]$Job = "migrate-seed",
    [string]$Stack = "infra/envs/dev"
)

$ErrorActionPreference = "Stop"

function Get-Output([string]$Name) {
    $value = terraform "-chdir=$Stack" output -raw $Name
    if ($LASTEXITCODE -ne 0 -or -not $value) { throw "terraform output $Name failed. Is the dev stack applied?" }
    return $value.Trim()
}

$cluster = Get-Output "ecs_cluster"
$sg = Get-Output "app_security_group_id"
$subnets = (terraform "-chdir=$Stack" output -json public_subnet_ids | ConvertFrom-Json) -join ","
$family = "$cluster-migrate-seed"
$network = "awsvpcConfiguration={subnets=[$subnets],securityGroups=[$sg],assignPublicIp=ENABLED}"

$runArgs = @("ecs", "run-task", "--cluster", $cluster, "--launch-type", "FARGATE",
    "--task-definition", $family, "--network-configuration", $network,
    "--query", "tasks[0].taskArn", "--output", "text")

$overrideFile = $null
if ($Job -eq "hashes") {
    # The command is replaced through a JSON file: inline JSON loses its quotes in Windows PowerShell.
    $overrideFile = [System.IO.Path]::GetTempFileName()
    $json = '{"containerOverrides":[{"name":"migrate-seed","command":["python","-m","seed.hashes"]}]}'
    [System.IO.File]::WriteAllText($overrideFile, $json)
    $runArgs += @("--overrides", "file://$overrideFile")
}

Write-Host "Starting $Job on cluster $cluster ..."
$taskArn = (& aws @runArgs).Trim()
if ($LASTEXITCODE -ne 0 -or -not $taskArn -or $taskArn -eq "None") { throw "aws ecs run-task failed" }
if ($overrideFile) { Remove-Item $overrideFile -ErrorAction SilentlyContinue }
$taskId = $taskArn.Split("/")[-1]
Write-Host "Task $taskId started. Waiting until it stops (1-3 minutes) ..."

aws ecs wait tasks-stopped --cluster $cluster --tasks $taskArn
if ($LASTEXITCODE -ne 0) { throw "Timed out waiting for task $taskId" }

$exitCode = aws ecs describe-tasks --cluster $cluster --tasks $taskArn --query "tasks[0].containers[0].exitCode" --output text
$reason = aws ecs describe-tasks --cluster $cluster --tasks $taskArn --query "tasks[0].stoppedReason" --output text

Write-Host ""
Write-Host "----- log of $Job -----"
$group = "/ecs/$cluster/migrate-seed"
$stream = "migrate-seed/migrate-seed/$taskId"
$messages = aws logs get-log-events --log-group-name $group --log-stream-name $stream --start-from-head --query "events[].message" --output json | ConvertFrom-Json
foreach ($line in $messages) { Write-Host $line }
Write-Host "-----------------------"
Write-Host "Exit code: $exitCode   Stopped reason: $reason"

if ($exitCode -ne "0") { exit 1 }
