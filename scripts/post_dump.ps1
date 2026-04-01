# POST a datadump to the ingest endpoint.
# Usage:
#   .\post_dump.ps1 [dump.json]
#   .\post_dump.ps1 --prod [dump.json]
#   .\post_dump.ps1 --kinds quests [dump.json]   # quests only (full quest list)
#   .\post_dump.ps1 --kinds quests:139 [dump.json]   # single quest by Id
#   .\post_dump.ps1 --kinds "quests:Clear 3 {dispatchKey} Dungeons" [dump.json]   # exact Name from pq-datadump.json (quote if spaces)
#   .\post_dump.ps1 --kinds skins,quests [dump.json]
#   .\post_dump.ps1 --kinds items:Chest [dump.json]   # TypeHierarchy exact string "Chest"
#   .\post_dump.ps1 --kinds items:634 [dump.json]    # single item by Id
#   .\post_dump.ps1 --kinds locations:634 [dump.json]   # single location by Id
#   .\post_dump.ps1 --kinds "locations:Cherry Blossom" [dump.json]   # exact location Name (quote if spaces)
#   .\post_dump.ps1 --kinds biomes:2 [dump.json]   # single biome by Id
#   .\post_dump.ps1 --kinds "biomes:Cherry Blossom" [dump.json]   # exact biome Name (quote if spaces)
#   .\post_dump.ps1 --kinds entities:497 [dump.json]   # single entity by Id (or entities:Name for exact name)
#   .\post_dump.ps1 --kinds skins:Tank [dump.json]   # skin named Tank (or skins:123 for id)
#   .\post_dump.ps1 --force-overwrite [dump.json]   # same as FORCE_OVERWRITE=1 for this POST (?force_overwrite=1)
#   .\post_dump.ps1 --edit-summary "Custom wiki edit summary" [dump.json]   # ?edit_summary= (URL-encoded)
# Env: $env:DATADUMP_INGEST_SECRET
#      $env:INGEST_URL (optional; default http://localhost:8081/ingest; ignored when --prod)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ScriptDir "..")

$Prod = $false
$Kinds = $null
$EditSummary = $null
$ForceOverwrite = $false
$Rest = [System.Collections.ArrayList]@()
for ($i = 0; $i -lt $args.Count; $i++) {
    $a = $args[$i]
    if ($a -eq "--prod") {
        $Prod = $true
    } elseif ($a -eq "--kinds" -and ($i + 1) -lt $args.Count) {
        $i++
        $Kinds = $args[$i]
    } elseif ($a -eq "--edit-summary" -and ($i + 1) -lt $args.Count) {
        $i++
        $EditSummary = $args[$i]
    } elseif ($a -eq "--force-overwrite" -or $a -eq "--force") {
        $ForceOverwrite = $true
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
    $KindsEnc = [System.Uri]::EscapeDataString($Kinds)
    if ($Url.Contains("?")) {
        $Url = "$Url&kinds=$KindsEnc"
    } else {
        $Url = "$Url`?kinds=$KindsEnc"
    }
}

if ($ForceOverwrite) {
    if ($Url.Contains("?")) {
        $Url = "$Url&force_overwrite=1"
    } else {
        $Url = "$Url`?force_overwrite=1"
    }
}

if ($EditSummary) {
    $SummaryEnc = [System.Uri]::EscapeDataString($EditSummary)
    if ($Url.Contains("?")) {
        $Url = "$Url&edit_summary=$SummaryEnc"
    } else {
        $Url = "$Url`?edit_summary=$SummaryEnc"
    }
}

Write-Host "POSTing $Dump to $Url ..."
$body = Get-Content $Dump -Raw
Invoke-RestMethod -Uri $Url -Method Post -Headers @{
    "Authorization" = "Bearer $Token"
    "Content-Type"  = "application/json"
} -Body $body | ConvertTo-Json -Depth 10
