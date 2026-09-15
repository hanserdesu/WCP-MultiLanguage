param(
    [string]$HostLabel = 'Windows PowerShell'
)

$ErrorActionPreference = 'Stop'

$version = $PSVersionTable.PSVersion.ToString()
Write-Host "运行环境：$HostLabel $version" -ForegroundColor DarkCyan
$installScript = Join-Path $PSScriptRoot 'Install-WCP-Japanese.ps1'
$success = $false

try {
    & $installScript
    $success = $true
} catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host '安装没有完成。请保留此窗口中的错误信息，便于排查。' -ForegroundColor Yellow
}

Write-Host ''
if ($success) {
    Write-Host '安装成功。请重新启动万词破。' -ForegroundColor Green
} else {
    Write-Host '安装失败。' -ForegroundColor Red
}
Write-Host '窗口将保持打开，请点击右上角 X 关闭；按 Enter 不会关闭窗口。' -ForegroundColor Yellow
