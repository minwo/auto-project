param(
    [Parameter(Mandatory = $true)]
    [string]$TunnelToken
)

$ErrorActionPreference = "Stop"

$Cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $Cloudflared) {
    Write-Host "cloudflared is not installed."
    Write-Host "Install it with: winget install --id Cloudflare.cloudflared"
    exit 1
}

Write-Host "Installing Cloudflare Tunnel as a Windows service..."
Write-Host "This command should be run from an Administrator terminal."
cloudflared service install $TunnelToken

Write-Host ""
Write-Host "Cloudflare Tunnel service install command completed."
Write-Host "Check status with: sc.exe query cloudflared"
