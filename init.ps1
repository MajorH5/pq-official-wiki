$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Test-Path .env)) {
    Write-Error "Missing .env file. Copy .env.example and fill in values."
    exit 1
}

Write-Host "Starting Pixel Quest Wiki stack..."
docker compose up -d --build

Write-Host ""
Write-Host "Services started:"
Write-Host "  Wiki:      http://localhost:8080"
Write-Host "  Ingest:    http://localhost:8081"
Write-Host ""
Write-Host "Stop with: docker compose down"
