param(
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendRoot = Join-Path $Root "frontend"
$RuntimeRoot = Join-Path $Root ".runtime"

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

function Import-RootEnv {
    param([string]$EnvPath)

    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return
    }

    Get-Content -LiteralPath $EnvPath -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

function Stop-PortProcess {
    param([int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    if (-not $processIds) {
        $processIds = netstat -ano |
            Select-String ":$Port\s" |
            ForEach-Object {
                $parts = ($_ -replace '^\s+', '') -split '\s+'
                if ($parts.Length -ge 5 -and $parts[3] -eq "LISTENING") {
                    [int]$parts[4]
                }
            } |
            Select-Object -Unique
    }

    foreach ($processId in $processIds) {
        if (-not $processId) {
            continue
        }
        try {
            $process = Get-Process -Id $processId -ErrorAction Stop
            Write-Host "Stopping port $Port process: $($process.ProcessName) ($processId)"
            Stop-Process -Id $processId -Force -ErrorAction Stop
        } catch {
            Write-Host "Port $Port process $processId already stopped or cannot be stopped."
        }
    }
}

function Start-HiddenCommand {
    param(
        [string]$WorkingDirectory,
        [string]$Command,
        [string]$LogPath
    )

    $argument = "/c $Command > `"$LogPath`" 2>&1"
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList $argument `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden | Out-Null
}

Write-Host "Restarting Domestic Stock MVP dev servers..."

Import-RootEnv -EnvPath (Join-Path $Root ".env")

Stop-PortProcess -Port $ApiPort
Stop-PortProcess -Port $FrontendPort

Start-Sleep -Seconds 1

$ApiLog = Join-Path $RuntimeRoot "fastapi.log"
$FrontendLog = Join-Path $RuntimeRoot "next.log"

Start-HiddenCommand `
    -WorkingDirectory $Root `
    -Command "python -m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort" `
    -LogPath $ApiLog

Start-HiddenCommand `
    -WorkingDirectory $FrontendRoot `
    -Command "npm run dev -- --hostname 127.0.0.1 --port $FrontendPort" `
    -LogPath $FrontendLog

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "FastAPI:  http://127.0.0.1:$ApiPort"
Write-Host "Next.js:  http://127.0.0.1:$FrontendPort"
Write-Host "API log:  $ApiLog"
Write-Host "Web log:  $FrontendLog"
Write-Host ""

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:$FrontendPort" | Out-Null
}

Write-Host "Done. You can close this window."
