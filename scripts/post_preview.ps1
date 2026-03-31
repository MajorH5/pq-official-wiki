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

$Token = $env:DATADUMP_INGEST_SECRET
if (-not $Token) {
    Write-Error "Set `$env:DATADUMP_INGEST_SECRET"
    exit 1
}

if (-not (Test-Path $Dump)) {
    Write-Error "File not found: $Dump"
    exit 1
}

$MaxChanges = $env:PREVIEW_MAX_CHANGES
if (-not $MaxChanges) { $MaxChanges = "50" }
$MaxDiffChars = $env:PREVIEW_MAX_DIFF_CHARS
if (-not $MaxDiffChars) { $MaxDiffChars = "50000" }

if ($Prod) {
    $UrlBase = "http://wiki.playpixelquest.com:8081/preview"
} elseif ($env:PREVIEW_URL) {
    $UrlBase = $env:PREVIEW_URL
} else {
    $UrlBase = "http://localhost:8081/preview"
}

# Guard against bad PREVIEW_URL values (e.g. "=50"); fall back to localhost.
if (-not $UrlBase -or -not ($UrlBase -like "http*")) {
    $UrlBase = "http://localhost:8081/preview"
}

$Url = "$UrlBase`?max_changes=$MaxChanges&max_diff_chars=$MaxDiffChars"
if ($Kinds) {
    $Url = "$Url&kinds=$Kinds"
}

Write-Host "POSTing $Dump to $Url ..."
$body = Get-Content $Dump -Raw
Invoke-RestMethod -Uri $Url -Method Post -Headers @{
    "Authorization" = "Bearer $Token"
    "Content-Type"  = "application/json"
} -Body $body | ConvertTo-Json -Depth 10

