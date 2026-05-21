param(
    [string]$Date = (Get-Date -Format "yyyy-MM-dd"),
    [string]$CodesFile = "data\stock_codes.txt",
    [switch]$FromMaster,
    [string[]]$Market = @("KOSPI", "KOSDAQ"),
    [int]$Limit = 0,
    [double]$Sleep = 0.2,
    [double]$MinScore = 60.0
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RuntimeRoot = Join-Path $Root ".runtime"
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

$LogDate = $Date.Replace("-", "")
$LogPath = Join-Path $RuntimeRoot "eod-batch-$LogDate.log"
$KiwoomDate = $Date.Replace("-", "")

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
        if ($key) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Name"
    Write-Host "python $($Arguments -join ' ')"
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Push-Location $Root
try {
    Import-RootEnv -EnvPath (Join-Path $Root ".env")
    Start-Transcript -Path $LogPath -Append | Out-Null

    Write-Host "Domestic Stock MVP EOD batch"
    Write-Host "Root: $Root"
    Write-Host "Date: $Date"

    $priceArgs = @(
        "-m",
        "app.scripts.load_kiwoom_daily_prices_many",
        "--date",
        $KiwoomDate,
        "--sleep",
        "$Sleep"
    )

    if ($FromMaster) {
        $priceArgs += "--from-master"
        foreach ($marketName in $Market) {
            $priceArgs += @("--market", $marketName)
        }
        if ($Limit -gt 0) {
            $priceArgs += @("--limit", "$Limit")
        }
    } else {
        $priceArgs += @("--codes-file", $CodesFile)
    }

    Invoke-Step -Name "Load Kiwoom daily prices" -Arguments $priceArgs

    Invoke-Step -Name "Load Kiwoom index daily prices" -Arguments @(
        "-m",
        "app.scripts.load_kiwoom_index_daily_prices",
        "--date",
        $KiwoomDate
    )

    if ($env:DART_API_KEY) {
        Invoke-Step -Name "Load DART disclosures" -Arguments @(
            "-m",
            "app.scripts.load_dart_disclosures",
            "--date",
            $Date
        )
    } else {
        Write-Host "DART_API_KEY is not set in process environment. Skipping DART disclosure load."
    }

    Invoke-Step -Name "Run daily scoring batch" -Arguments @(
        "-m",
        "app.scripts.run_daily_batch",
        "--date",
        $Date,
        "--history-limit",
        "90",
        "--min-score",
        "$MinScore"
    )

    Write-Host ""
    Write-Host "EOD batch completed."
    Write-Host "Log: $LogPath"
} finally {
    try {
        Stop-Transcript | Out-Null
    } catch {
    }
    Pop-Location
}
