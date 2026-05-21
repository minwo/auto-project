param(
    [string]$TaskName = "AutoProjectEodBatch",
    [string]$Time = "16:30"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BatchScript = Join-Path $Root "scripts\run-eod-batch.ps1"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Action = "`"$PowerShell`" -NoProfile -ExecutionPolicy Bypass -File `"$BatchScript`""

schtasks.exe /Create `
    /TN $TaskName `
    /TR $Action `
    /SC WEEKLY `
    /D MON,TUE,WED,THU,FRI `
    /ST $Time `
    /F | Out-Host

Write-Host ""
Write-Host "Scheduled task installed."
Write-Host "Task: $TaskName"
Write-Host "Time: $Time, Monday-Friday"
Write-Host "Action: $Action"
