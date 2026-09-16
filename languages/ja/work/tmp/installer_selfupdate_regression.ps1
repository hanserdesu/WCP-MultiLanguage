# Self-update full regression (PS 5.1):
# T1 same version -> no prompt, no download, continues install
# T2 newer version + 'y' -> downloads stub pkg, SHA verify, extract, launch new cmd, exit 0
# T3 newer version + 'n' -> skip update, continue
# T4 fetch fail -> graceful continue
$ErrorActionPreference = 'Stop'
$repoRoot = 'D:\ATooManyLanguage\Japanese'
$text = Get-Content -LiteralPath (Join-Path $repoRoot 'wcp_wordbooks\installer\Install-WCP-Japanese.ps1') -Raw -Encoding UTF8
foreach ($fnName in @('Write-Step','Get-Sha256','Fail','Get-InstallerErrorLogPath','Write-InstallerErrorLog','Show-ExtractFailure','Copy-TreeNet','Get-ExtendedPath','Remove-TreeNet','Backup-PackWithoutAudio','Remove-LegacyRedundancy')) {
    $s = $text.IndexOf("function $fnName")
    if ($s -ge 0) {
        $after = $text.IndexOf("`nfunction ", $s + 10)
        if ($after -lt 0) { $after = $text.Length }
        Invoke-Expression $text.Substring($s, $after - $s)
    }
}
$s = $text.IndexOf('# ---- 安装器自更新')
$e = $text.IndexOf('Write-Host "磁盘空间检查通过')
if ($s -lt 0 -or $e -lt 0) { throw 'self-update block not found' }
$block = $text.Substring($s, $e - $s)
$stage = Join-Path $env:TEMP ('wcp-selfupd2-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'wcp') | Out-Null
$dataDir = Join-Path $stage 'wcp'
$fail = 0

function global:Download-WithProgress([string]$uri, [string]$destination, [string]$displayName, [int64]$expectedSize) {
    $global:DownloadedUrl = $uri
    $stubPkg = Join-Path $env:TEMP ('stubpkg-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path (Join-Path $stubPkg 'WCP日语词书安装包') | Out-Null
    [IO.File]::WriteAllText((Join-Path $stubPkg 'WCP日语词书安装包\01_双击运行我.cmd'), "@echo ok`r`n")
    Compress-Archive -Path (Join-Path $stubPkg '*') -DestinationPath $destination -Force
    Remove-Item -LiteralPath $stubPkg -Recurse -Force
}
function global:Expand-ZipWithProgress([string]$zipPath, [string]$destination, [string]$displayName) {
    Expand-Archive -LiteralPath $zipPath -DestinationPath $destination -Force
    $global:ExpandedUpdate = $true
}
function global:Start-Process { param($FilePath, $WorkingDirectory)
    $global:LaunchedCmd = $FilePath
    # 模拟真实 cmd 启动后：安装器脚本会 exit 0 结束当前进程。
    # 测试中不能真的退出（还要跑 T3/T4），改用特殊异常向上传播并标记已切换。
    $global:SimulatedExit = $true
    throw [System.Management.Automation.ExitException]::new(0)
}

$stubSha = 'A' * 64
function New-Index([string]$version, [string]$sha, [int64]$size) {
    @{ main_release=$version; installer_version=$version;
       core_installer=@{ name='stub-core.zip'; sha256=$sha; size=$size };
       resource_manifest='release-manifest.json' } | ConvertTo-Json
}
# answer provider: queue of answers for Read-Host
$global:Answers = New-Object System.Collections.Generic.Queue[string]
function global:Read-Host { param($Prompt) if ($global:Answers.Count -gt 0) { $global:Answers.Dequeue() } else { '' } }

function Run-Block([string]$indexFile, [string]$selfVer) {
    $env:WCP_INSTALLER_VERSION = $selfVer
    $b = $block.Replace('https://github.com/hanserdesu/japanese/releases/download/wcp-jp-resources-v1.1.0/release-index.json', ($indexFile -replace '\\','/'))
    # $data/$stamp 必须在 Run-Block 作用域可见（Invoke-Expression 继承当前作用域）
    $data = $dataDir
    $stamp = 'test_stamp'
    # SHA stub：T2 用任意可匹配值；测试只验证流程不验证真实哈希
    function global:Get-Sha256([string]$path) {
        if ($path -like '*stub-core.zip') { return 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' }
    }
    Invoke-Expression $b
}

# --- T1: same version ---
$idx1 = Join-Path $stage 'idx_same.json'
[IO.File]::WriteAllText($idx1, (New-Index 'wcp-jp-v1.2.7' $stubSha 100), (New-Object Text.UTF8Encoding($false)))
try {
    # 同版本根本不会询问（Read-Host 不该被调用）；不留队列残留
    Run-Block $idx1 'wcp-jp-v1.2.7'
    if ($global:LaunchedCmd) { Write-Host 'T1 FAIL: launched update for same version'; $fail = 1 }
    else { Write-Host 'T1 PASS (same version, no update)' }
} catch { Write-Host ("T1 FAIL: " + $_.Exception.Message); $fail = 1 }

# --- T2: newer version + y ---
$idx2 = Join-Path $stage 'idx_new.json'
$sha2 = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
[IO.File]::WriteAllText($idx2, (New-Index 'wcp-jp-v1.2.8' $sha2 100), (New-Object Text.UTF8Encoding($false)))
$global:LaunchedCmd = $null; $global:ExpandedUpdate = $false
$global:Answers.Enqueue('y')
try {
    Run-Block $idx2 'wcp-jp-v1.2.7'
    if ($global:LaunchedCmd -and ($global:LaunchedCmd -like '*01_双击运行我.cmd')) {
        Write-Host 'T2 PASS (newer version accepted: download -> verify -> extract -> launch)'
    } else {
        Write-Host ("T2 FAIL: launched = " + $global:LaunchedCmd); $fail = 1
    }
} catch { Write-Host ("T2 FAIL: " + $_.Exception.Message); $fail = 1 }

# --- T3: newer version + n ---
$global:LaunchedCmd = $null
$global:Answers.Enqueue('n')
try {
    Run-Block $idx2 'wcp-jp-v1.2.7'
    if (-not $global:LaunchedCmd) { Write-Host 'T3 PASS (declined, continues install)' }
    else { Write-Host 'T3 FAIL: launched despite decline'; $fail = 1 }
} catch { Write-Host ("T3 FAIL: " + $_.Exception.Message); $fail = 1 }

# --- T4: index fetch fails (nonexistent file) ---
$global:LaunchedCmd = $null
try {
    Run-Block (Join-Path $stage 'no_such_index.json') 'wcp-jp-v1.2.7'
    Write-Host 'T4 PASS (fetch failure tolerated)'
} catch { Write-Host ("T4 FAIL: " + $_.Exception.Message); $fail = 1 }

Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
if ($fail -eq 0) { Write-Host 'SELF-UPDATE REGRESSION ALL PASS' } else { exit 1 }
