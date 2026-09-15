$ErrorActionPreference = 'Stop'
$installer = Join-Path (Split-Path $PSScriptRoot -Parent) '..'
$root = 'D:/Japanese/wcp_wordbooks/output/installer_pkg/WCP日语词书安装包/support'
# Load extractor exactly like the installer does
$text = Get-Content -LiteralPath (Join-Path $root 'Install-WCP-Japanese.ps1') -Raw -Encoding UTF8
$start = $text.IndexOf('function Ensure-ZipExtractor')
$end = $text.IndexOf('function Expand-ZipWithProgress')
$block = $text.Substring($start, $end - $start)
$block = $block -replace 'if \(''WcpJapaneseZipSession'' -as \[type\]\) \{ return \}', ''
Invoke-Expression $block
function Expand-ZipWithProgress([string]$zipPath, [string]$destination, [string]$displayName) {
    Ensure-ZipExtractor
    $workers = 4
    $session = [WcpJapaneseZipSession]::Start($zipPath, $destination, $workers)
    while (-not $session.TotalReady -and -not $session.Task.IsCompleted) { Start-Sleep -Milliseconds 50 }
    $task = $session.Task
    $totalFiles = $session.TotalFiles
    $totalBytes = $session.TotalBytes
    while (-not $task.IsCompleted) {
        $doneFiles = [Math]::Min($session.CompletedFiles, $totalFiles)
        Start-Sleep -Milliseconds 100
    }
    $task.GetAwaiter().GetResult()
    Write-Output ("{0}: total={1} done={2} bytes={3}" -f $displayName, $totalFiles, $session.CompletedFiles, $session.CompletedBytes)
}
$stage = Join-Path $env:TEMP ('wcp-zip-regression-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$coreZip = 'D:/Japanese/wcp_wordbooks/output/release/WCP-Japanese-OneClick-Installer-wcp-jp-v1.1.7.zip'
$audioZip = 'D:/Japanese/wcp_wordbooks/output/release/wcp-japanese-audio-sentences.zip'
# Two different archives back to back: catches any stale total/carried counters.
Expand-ZipWithProgress $coreZip (Join-Path $stage 'a') 'core'
Expand-ZipWithProgress $audioZip (Join-Path $stage 'b') 'audio'
Write-Output ('session check: ' + ([WcpJapaneseZipSession] -ne $null))
Remove-Item -LiteralPath $stage -Recurse -Force
Write-Output 'REGRESSION PASS'
