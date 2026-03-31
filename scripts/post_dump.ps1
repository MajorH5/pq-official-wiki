# POST a datadump to the ingest endpoint.
# Usage:
#   .\post_dump.ps1 [dump.json]
#   .\post_dump.ps1 --prod [dump.json]
#   .\post_dump.ps1 --kinds skins,quests [dump.json]
# Env: $env:DATADUMP_INGEST_SECRET
#      $env:INGEST_URL (optional; default http://localhost:8081/ingest; ignored when --prod)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ScriptDir "..")

$Prod = $false
$Kinds = $null
$Rest = [System.Collections.ArrayList]@()
for ($i = 0; $i -lt $args.Count; $i++) {
    $a = $args[$i]
    if ($a -eq "--prod") {
        $Prod = $true
    } elseif ($a -eq "--kinds" -and ($i + 1) -lt $args.Count) {
        $i++
        $Kinds = $args[$i]
    } else {
        [void]$Rest.Add($a)
    }
}

$Dump = if ($Rest.Count -gt 0) { $Rest[0] } else { "pq-datadump.json" }
$Url = if ($Prod) {
    "http://wiki.playpixelquest.com:8081/ingest"
} elseif ($env:INGEST_URL) {
    $env:INGEST_URL
} else {
    "http://localhost:8081/ingest"
}
$Token = $env:DATADUMP_INGEST_SECRET

if (-not $Token) {
    Write-Error "Set `$env:DATADUMP_INGEST_SECRET"
    exit 1
}

if (-not (Test-Path $Dump)) {
    Write-Error "File not found: $Dump"
    exit 1
}

if ($Kinds) {
    if ($Url -like "*`?*") {
        $Url = "$Url&kinds=$Kinds"
    } else {
        $Url = "$Url`?kinds=$Kinds"
    }
}

Write-Host "POSTing $Dump to $Url ..."
$body = Get-Content $Dump -Raw
Invoke-RestMethod -Uri $Url -Method Post -Headers @{
    "Authorization" = "Bearer $Token"
    "Content-Type"  = "application/json"
} -Body $body | ConvertTo-Json -Depth 10
