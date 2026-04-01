# Request a Pixel Quest wiki ↔ Roblox link code (PixelQuestRoblox API).
# Usage:
#   .\scripts\pq_roblox_request_code.ps1 <robloxUserId>
#   .\scripts\pq_roblox_request_code.ps1 <robloxUserId> --prod
# Env: WIKI_BASE_URL (default http://localhost:8080; ignored when --prod), PQ_API_SECRET or DATADUMP_INGEST_SECRET

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ScriptDir "..")

$Prod = $false
$Rest = [System.Collections.ArrayList]@()
for ($i = 0; $i -lt $args.Count; $i++) {
    $a = $args[$i]
    if ($a -eq "--prod") {
        $Prod = $true
    } else {
        [void]$Rest.Add($a)
    }
}

$RobloxId = if ($Rest.Count -gt 0) { $Rest[0] } else { $env:ROBLOX_USER_ID }
if (-not $RobloxId) {
    Write-Error "Usage: .\scripts\pq_roblox_request_code.ps1 <robloxUserId> [--prod]"
    exit 1
}

$Base = if ($Prod) {
    "https://wiki.playpixelquest.com"
} elseif ($env:WIKI_BASE_URL) {
    $env:WIKI_BASE_URL.TrimEnd("/")
} else {
    "http://localhost:8080"
}
$Token = if ($env:PQ_API_SECRET) { $env:PQ_API_SECRET } else { $env:DATADUMP_INGEST_SECRET }

if (-not $Token) {
    Write-Error "Set `$env:PQ_API_SECRET or `$env:DATADUMP_INGEST_SECRET"
    exit 1
}

$Uri = "$Base/api.php"
$Body = "action=pqrobloxrequestcode&format=json&robloxuserid=$RobloxId"

Write-Host "POST $Uri (robloxuserid=$RobloxId) ..."
Invoke-RestMethod -Uri $Uri -Method Post `
    -ContentType "application/x-www-form-urlencoded" `
    -Headers @{ "X-PQ-API-Secret" = $Token } `
    -Body $Body | ConvertTo-Json -Depth 10
