# 双击入口回归测试（离线、不碰游戏目录）。
#
# 背景缺陷（2026-09-21）：仓库根的「一键安装词书.cmd」有 --keep-open 自重启，
# 但 tools/release/build_installer.py 打包时另写了一份两行 cmd 覆盖它，那份没有
# 任何保持窗口的机制，玩家双击后安装一结束窗口就消失，看不到任何状态输出。
#
# 本测试用桩包（复制真实入口 cmd + 桩 run-installer.ps1）验证：
#   A. 安装入口：桩脚本跑完后仍有 keep-open 的 cmd 进程存活（窗口保留）；
#   B. 更新入口：同上，且桩脚本确实收到 -Update；
#   C. 反向对照：没有 --keep-open 包装的两行 cmd 跑完后不留进程
#      （这正是修复前打包产物的行为，用来证明本测试对缺陷敏感）。
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $here '..')).Path

$pass = 0; $fail = 0
function Check([string]$name, [bool]$cond) {
    if ($cond) { $script:pass++; Write-Host ("  PASS  " + $name) }
    else { $script:fail++; Write-Host ("  FAIL  " + $name) }
}

$stubBody = @'
$marker = Join-Path $PSScriptRoot 'stub-ran.txt'
$lines = @(
    ('args=' + ($args -join ',')),
    ('keep_open=' + $env:WCP_KEEP_OPEN)
)
[IO.File]::WriteAllText($marker, [string]::Join([char]10, $lines))
'@

function New-StubPackage([string]$name, [bool]$withLegacyLauncher) {
    $dir = Join-Path $script:tempRoot $name
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $script:repoRoot '一键安装词书.cmd') -Destination $dir
    Copy-Item -LiteralPath (Join-Path $script:repoRoot '更新词书资源.cmd') -Destination $dir
    [IO.File]::WriteAllText((Join-Path $dir 'run-installer.ps1'), $stubBody, (New-Object Text.UTF8Encoding($true)))
    if ($withLegacyLauncher) {
        # 复刻修复前的打包产物：没有 --keep-open 自重启的两行入口。
        $nl = [string]([char]13) + [string]([char]10)
        $legacy = '@echo off' + $nl +
            'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-installer.ps1"' + $nl
        [IO.File]::WriteAllText((Join-Path $dir 'legacy-no-keep-open.cmd'), $legacy, (New-Object Text.ASCIIEncoding))
    }
    return $dir
}

function Get-StubCmdProcesses([string]$dir) {
    $pattern = '*' + $dir + '*'
    return @(Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like $pattern })
}

function Invoke-StubLauncher([string]$dir, [string]$cmdName) {
    $marker = Join-Path $dir 'stub-ran.txt'
    if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker -Force }
    $cmdPath = Join-Path $dir $cmdName
    Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d', '/c', ('"' + $cmdPath + '"')) -WindowStyle Hidden | Out-Null
    # 等桩脚本落地标记（说明安装流程确实跑完并返回了批处理），再多给 2 秒让窗口状态稳定。
    for ($i = 0; $i -lt 100 -and -not (Test-Path -LiteralPath $marker); $i++) { Start-Sleep -Milliseconds 100 }
    if (-not (Test-Path -LiteralPath $marker)) { return $null }
    Start-Sleep -Seconds 2
    # @() 包一层：空结果从函数返回时会变成 $null，直接取 .Count 会踩严格模式。
    $procs = @(Get-StubCmdProcesses $dir)
    $result = @{ Output = (Get-Content -LiteralPath $marker -Raw); ProcCount = $procs.Count; Procs = $procs }
    foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    return $result
}

$tempRoot = Join-Path $env:TEMP ('wcp_launcher_test_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $installDir = New-StubPackage 'install' $false
    $installRun = Invoke-StubLauncher $installDir '一键安装词书.cmd'
    Check 'A. 安装入口跑完后窗口进程仍在（keep-open 生效）' ($installRun -and $installRun.ProcCount -gt 0)
    Check 'A. 安装入口向 run-installer.ps1 传了 WCP_KEEP_OPEN=1' ($installRun -and $installRun.Output -match 'keep_open=1')

    $updateDir = New-StubPackage 'update' $false
    $updateRun = Invoke-StubLauncher $updateDir '更新词书资源.cmd'
    Check 'B. 更新入口跑完后窗口进程仍在（keep-open 生效）' ($updateRun -and $updateRun.ProcCount -gt 0)
    Check 'B. 更新入口把 -Update 转发给 run-installer.ps1' ($updateRun -and $updateRun.Output -match 'args=-Update')

    $legacyDir = New-StubPackage 'legacy' $true
    $legacyRun = Invoke-StubLauncher $legacyDir 'legacy-no-keep-open.cmd'
    Check 'C. 反向对照：无 keep-open 包装的入口跑完后不留进程' ($legacyRun -and $legacyRun.ProcCount -eq 0)
} finally {
    foreach ($dir in @($installDir, $updateDir, $legacyDir)) {
        if (-not $dir) { continue }
        foreach ($p in (Get-StubCmdProcesses $dir)) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
        foreach ($f in @('一键安装词书.cmd', '更新词书资源.cmd', 'run-installer.ps1', 'stub-ran.txt', 'legacy-no-keep-open.cmd')) {
            $target = Join-Path $dir $f
            if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue }
        }
        Remove-Item -LiteralPath $dir -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $tempRoot -Force -ErrorAction SilentlyContinue
}

Write-Host ('结果: {0} 通过, {1} 失败' -f $pass, $fail)
if ($fail -gt 0) { exit 1 } else { exit 0 }
