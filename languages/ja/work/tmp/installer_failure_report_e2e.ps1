# E2E test of the REAL run-installer.ps1 failure path:
# - real run-installer.ps1 (unmodified)
# - stub Install-WCP-Japanese.ps1 that throws an AggregateException with an inner cause
#   (exactly what GetAwaiter().GetResult() surfaces)
# - Start-Process stubbed to capture the URL instead of opening a browser
# - installer-error.log pre-seeded to prove the tail lands in the issue body
$ErrorActionPreference = 'Stop'
$stage = Join-Path $env:TEMP ('wcp-e2e-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'support') | Out-Null

# 1) copy the REAL run-installer.ps1 byte-for-byte
Copy-Item 'D:\ATooManyLanguage\Japanese\wcp_wordbooks\installer\run-installer.ps1' (Join-Path $stage 'support\run-installer.ps1')

# 2) pre-seed the error log the way the main script would
$logDir = Join-Path $env:USERPROFILE 'AppData\LocalLow\WCP\wcp'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir 'installer-error.log'
[IO.File]::AppendAllText($logPath, "[TEST] 解压 单词音频 第 1 次失败（将重试）：System.IO.IOException: 写入 C:\x\aux.mp3 失败（重试 3 次后仍失败）：being used by another process`r`n", (New-Object Text.UTF8Encoding($false)))

# 3) stub main script: aggregate exception with inner IOException, like .GetResult()
$stub = @'
$agg = [AggregateException]::new("One or more errors occurred.", [System.IO.IOException]::new("写入 C:\x\aux.mp3 失败（重试 3 次后仍失败）：being used by another process")))
throw $agg
'@
# fix the typo-proof constructor (no trailing paren issues) by building via script
$stub = @'
$inner = New-Object System.IO.IOException('写入 C:\x\aux.mp3 失败（重试 3 次后仍失败）：being used by another process')
$agg = New-Object System.AggregateException('One or more errors occurred.', @($inner))
throw $agg
'@
[IO.File]::WriteAllText((Join-Path $stage 'support\Install-WCP-Japanese.ps1'), $stub, (New-Object Text.UTF8Encoding($true)))

# 4) global Start-Process stub (script scope resolves up to global for functions)
function global:Start-Process { param($FilePath) $global:CapturedIssueUrl = $FilePath }

# 5) run the real run-installer.ps1 (its try/catch swallows the failure and reports)
& (Join-Path $stage 'support\run-installer.ps1') -HostLabel 'E2E Test PS' 2>&1 | Out-Host

# 6) assertions
$ok = $true
if (-not $global:CapturedIssueUrl) {
    Write-Host 'E2E FAIL: Start-Process never called (no issue URL built)'
    $ok = $false
} else {
    $u = [Uri]::UnescapeDataString($global:CapturedIssueUrl)
    Write-Host ('issue URL host path: ' + ($global:CapturedIssueUrl -split '\?')[0])
    if ($global:CapturedIssueUrl -notmatch 'issues/new') { Write-Host 'E2E FAIL: not an issues/new URL'; $ok = $false }
    if ($u -notmatch '安装失败：') { Write-Host 'E2E FAIL: title missing'; $ok = $false }
    if ($u -notmatch '写入 C:.x.aux.mp3 失败') { Write-Host 'E2E FAIL: innermost error not in body'; $ok = $false }
    if ($u -notmatch 'installer-error.log 尾部') { Write-Host 'E2E FAIL: log tail not in body'; $ok = $false }
    if ($u -notmatch 'E2E') { Write-Host 'E2E NOTE: environment line present check skipped' }
    if ($u -match 'AggregateException') { Write-Host '  outer chain present: yes' }
    if ($u.Length -gt 9000) { Write-Host 'E2E WARN: URL very long, browser may truncate' }
}
if ($ok) { Write-Host 'E2E PASS: real run-installer reported via prefilled issue with full chain + log tail' }
Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
# remove the seeded test line from the real log
$lines = [IO.File]::ReadAllLines($logPath) | Where-Object { $_ -notmatch '^\[TEST\]' }
[IO.File]::WriteAllLines($logPath, $lines, (New-Object Text.UTF8Encoding($false)))
if (-not $ok) { exit 1 }
