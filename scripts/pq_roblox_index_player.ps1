# Index a Roblox player in the wiki search index (PixelQuestRoblox API).
# Usage: .\scripts\pq_roblox_index_player.ps1 <robloxUserId> [optionalUsername]
# Env: WIKI_BASE_URL (default http://localhost:8080), PQ_API_SECRET or DATADUMP_INGEST_SECRET

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ScriptDir "..")

$RobloxId = if ($args[0]) { $args[0] } else { $env:ROBLOX_USER_ID }
if (-not $RobloxId) {
    Write-Error "Usage: .\scripts\pq_roblox_index_player.ps1 <robloxUserId> [optionalUsername]"
    exit 1
}

$Base = if ($env:WIKI_BASE_URL) { $env:WIKI_BASE_URL.TrimEnd("/") } else { "http://localhost:8080" }
$Token = if ($env:PQ_API_SECRET) { $env:PQ_API_SECRET } else { $env:DATADUMP_INGEST_SECRET }

if (-not $Token) {
    Write-Error "Set `$env:PQ_API_SECRET or `$env:DATADUMP_INGEST_SECRET"
    exit 1
}

$Uri = "$Base/api.php"
$Body = "action=pqrobloxindexplayer&format=json&userid=$RobloxId"
if ($args[1]) {
    $u = [uri]::EscapeDataString($args[1])
    $Body += "&username=$u"
}

Write-Host "POST $Uri (userid=$RobloxId) ..."
Invoke-RestMethod -Uri $Uri -Method Post `
    -ContentType "application/x-www-form-urlencoded" `
    -Headers @{ "X-PQ-API-Secret" = $Token } `
    -Body $Body | ConvertTo-Json -Depth 10
