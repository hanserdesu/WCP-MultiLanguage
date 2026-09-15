param(
    [string]$HostLabel = "PowerShell"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installerScript = Join-Path $scriptDir "Install-WCP-Cantonese.ps1"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  《万词破-单词女友》粤语词书一键安装器" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $installerScript) {
    & $installerScript
} else {
    Write-Host "未找到安装主脚本: $installerScript" -ForegroundColor Red
}
