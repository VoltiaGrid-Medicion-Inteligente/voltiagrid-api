<#
.SYNOPSIS
  Runs one Spark job of voltiagrid-data as an ECS Fargate task on the S3 lake, prints its log, time and cost (US-40).

.DESCRIPTION
  Starts the task definition voltiagrid-dev-spark-jobs (infra/modules/spark_task) with the job as command:
      python -m jobs.<Job> <JobArgs> --raw $LAKE_RAW --clean $LAKE_CLEAN --curated $LAKE_CURATED
  The LAKE_* variables are set in the task definition, so the job reads and writes the S3 buckets of the data stack
  with the permissions of the Spark task role. It waits until the task stops (polling every 30 s, no time limit),
  prints the log, the exit code, how long it ran and what it cost (Fargate price per vCPU-hour and GB-hour).

  -Spot uses Fargate Spot (ADR-014: only the one-off history load). -Cpu and -Memory ask for a bigger task than the
  task definition (2 vCPU / 8 GB), for example 4096 and 16384.

.EXAMPLE
  .\infra\scripts\run-spark.ps1 -Job clean_readings -JobArgs "--source f3 --ingest-date 2026-11-04"
  .\infra\scripts\run-spark.ps1 -Job estimate_gaps -JobArgs "--run f3-2026-11-04"
  .\infra\scripts\run-spark.ps1 -Job clean_readings -JobArgs "--source f1 --mode full --ingest-date 2026-10-28" -Spot -Cpu 4096 -Memory 16384
#>
param(
    [Parameter(Mandatory = $true)][string]$Job,
    [string]$JobArgs = "",
    [switch]$Spot,
    [int]$Cpu = 0,
    [int]$Memory = 0,
    [string]$Stack = "infra/envs/dev",
    # Fargate Linux/x86 in us-east-1 (https://aws.amazon.com/fargate/pricing/, checked 2026-11). Spot changes with demand:
    # check the page before reporting a cost.
    [double]$VcpuHour = 0.04048,
    [double]$GbHour = 0.004445,
    [double]$SpotVcpuHour = 0.0127,
    [double]$SpotGbHour = 0.0014
)

$ErrorActionPreference = "Stop"

function Get-Output([string]$Name) {
    $value = terraform "-chdir=$Stack" output -raw $Name
    if ($LASTEXITCODE -ne 0 -or -not $value) { throw "terraform output $Name failed. Is the dev stack applied?" }
    return $value.Trim()
}

if ($Job -notmatch '^[a-z_0-9]+$') { throw "Job must be a module of jobs/, e.g. clean_readings" }

$cluster = Get-Output "ecs_cluster"
$family = Get-Output "spark_task_family"
$sg = Get-Output "app_security_group_id"
$subnets = (terraform "-chdir=$Stack" output -json public_subnet_ids | ConvertFrom-Json) -join ","
$network = "awsvpcConfiguration={subnets=[$subnets],securityGroups=[$sg],assignPublicIp=ENABLED}"

# The command goes through sh so the container expands $LAKE_*; the overrides go in a file because inline JSON
# loses its quotes in Windows PowerShell.
$shell = "python -m jobs.$Job $JobArgs --raw `$LAKE_RAW --clean `$LAKE_CLEAN --curated `$LAKE_CURATED"
$overrides = @{ containerOverrides = @(@{ name = "spark-jobs"; command = @("sh", "-c", $shell) }) }
if ($Cpu -gt 0) { $overrides.cpu = "$Cpu" }
if ($Memory -gt 0) { $overrides.memory = "$Memory" }
$overrideFile = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($overrideFile, ($overrides | ConvertTo-Json -Depth 5 -Compress))

$capacity = if ($Spot) { "FARGATE_SPOT" } else { "FARGATE" }
Write-Host "Starting jobs.$Job on $cluster ($capacity): $JobArgs"
$taskArn = (aws ecs run-task --cluster $cluster --task-definition $family `
        --capacity-provider-strategy "capacityProvider=$capacity,weight=1" `
        --network-configuration $network --overrides "file://$overrideFile" `
        --started-by "run-spark" --query "tasks[0].taskArn" --output text).Trim()
Remove-Item $overrideFile -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0 -or -not $taskArn -or $taskArn -eq "None") { throw "aws ecs run-task failed" }
$taskId = $taskArn.Split("/")[-1]
Write-Host "Task $taskId started. Waiting until it stops ..."

do {
    Start-Sleep -Seconds 30
    $status = (aws ecs describe-tasks --cluster $cluster --tasks $taskArn --query "tasks[0].lastStatus" --output text).Trim()
    Write-Host "  $(Get-Date -Format HH:mm:ss) $status"
} while ($status -ne "STOPPED")

$task = aws ecs describe-tasks --cluster $cluster --tasks $taskArn --output json | ConvertFrom-Json
$t = $task.tasks[0]
$exitCode = $t.containers[0].exitCode

Write-Host ""
Write-Host "----- log of jobs.$Job -----"
$group = "/ecs/$cluster/spark-jobs"
$stream = "spark-jobs/spark-jobs/$taskId"
$messages = aws logs get-log-events --log-group-name $group --log-stream-name $stream --start-from-head --query "events[].message" --output json | ConvertFrom-Json
foreach ($line in $messages) { Write-Host $line }
Write-Host "-----------------------"

# Fargate bills from the image pull until the task stops (per second, 1 minute minimum).
$started = [datetime]$t.pullStartedAt
$stopped = [datetime]$t.stoppedAt
$seconds = [math]::Max(60, ($stopped - $started).TotalSeconds)
$vcpu = [int]$t.cpu / 1024
$gb = [int]$t.memory / 1024
$priceV = if ($Spot) { $SpotVcpuHour } else { $VcpuHour }
$priceG = if ($Spot) { $SpotGbHour } else { $GbHour }
$cost = $seconds / 3600 * ($vcpu * $priceV + $gb * $priceG)
Write-Host ("Exit code: {0}   Stopped reason: {1}" -f $exitCode, $t.stoppedReason)
Write-Host ("Ran {0:N0} s on {1} vCPU / {2} GB ({3}): about {4:N4} USD" -f $seconds, $vcpu, $gb, $capacity, $cost)

if ("$exitCode" -ne "0") { exit 1 }
