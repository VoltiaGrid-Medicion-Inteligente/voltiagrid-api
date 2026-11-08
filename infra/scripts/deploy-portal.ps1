<#
.SYNOPSIS
  Builds the customer portal against the dev API and uploads it to S3 behind CloudFront (US-69, KAN-354).

.DESCRIPTION
  Reads the bucket and the distribution from the dev stack (terraform outputs), builds voltiagrid-portal with
  VITE_API_URL set to the API (alb_url), uploads dist/ and invalidates the CloudFront cache.
  The bucket is recreated and emptied by destroy.ps1, so run this again after every dev apply.

.PARAMETER PortalPath
  Folder of the voltiagrid-portal repo (a clone of develop, or of the feature branch to test).

.EXAMPLE
  .\infra\scripts\deploy-portal.ps1 -PortalPath ..\voltiagrid-portal
#>
param(
    [Parameter(Mandatory = $true)][string]$PortalPath,
    [string]$Stack = "infra/envs/dev"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path "infra/scripts/deploy-portal.ps1")) { throw "Run this script from the root of voltiagrid-api." }
if (-not (Test-Path (Join-Path $PortalPath "package.json"))) { throw "$PortalPath is not the voltiagrid-portal repo." }

$bucket = (terraform "-chdir=$Stack" output -raw portal_bucket_name).Trim()
$distribution = (terraform "-chdir=$Stack" output -raw portal_distribution_id).Trim()
$apiUrl = (terraform "-chdir=$Stack" output -raw alb_url).Trim()
if ($LASTEXITCODE -ne 0 -or -not $bucket) { throw "The portal is not in the dev stack yet: terraform apply first." }

Push-Location $PortalPath
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    $env:VITE_API_URL = $apiUrl
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }

    aws s3 sync dist/ "s3://$bucket/" --delete
    if ($LASTEXITCODE -ne 0) { throw "upload to s3://$bucket failed" }

    aws cloudfront create-invalidation --distribution-id $distribution --paths "/*" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "CloudFront invalidation failed" }
}
finally {
    Pop-Location
}

$url = (terraform "-chdir=$Stack" output -raw portal_url).Trim()
Write-Host "Portal uploaded. API: $apiUrl. Open: $url"
