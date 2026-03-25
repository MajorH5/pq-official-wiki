# POST a datadump to the ingest endpoint.
# Usage: .\post_dump.ps1 [dump.json]
# Env: $env:DATADUMP_INGEST_SECRET

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ScriptDir "..")

$Dump = if ($args[0]) { $args[0] } else { "pq-datadump.json" }
$Url = if ($env:INGEST_URL) { $env:INGEST_URL } else { "http://playpixelquest.com:8081/ingest" }
$Token = $env:DATADUMP_INGEST_SECRET

if (-not $Token) {
    Write-Error "Set `$env:DATADUMP_INGEST_SECRET"
    exit 1
}

if (-not (Test-Path $Dump)) {
    Write-Error "File not found: $Dump"
    exit 1
}

Write-Host "POSTing $Dump to $Url ..."
$body = Get-Content $Dump -Raw
Invoke-RestMethod -Uri $Url -Method Post -Headers @{
    "Authorization" = "Bearer $Token"
    "Content-Type"  = "application/json"
} -Body $body | ConvertTo-Json -Depth 10
