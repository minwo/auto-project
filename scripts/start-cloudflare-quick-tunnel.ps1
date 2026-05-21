param(
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue

if (-not $Cloudflared) {
    Write-Host "cloudflared is not installed."
    Write-Host "Install it with: winget install --id Cloudflare.cloudflared"
    exit 1
}

Write-Host "Starting project dev servers..."
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\restart-dev.ps1")

Write-Host ""
Write-Host "Starting a temporary Cloudflare quick tunnel."
Write-Host "Copy the trycloudflare.com URL and open it from your phone."
Write-Host "Press Ctrl+C to stop the tunnel."
Write-Host ""

cloudflared tunnel --url "http://127.0.0.1:$FrontendPort"
