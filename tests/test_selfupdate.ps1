# 自更新检查回归测试（离线：本地假 GitHub 回放 HTTP，不碰真实网络）。
#
# 背景缺陷（2026-09-21 实测）：索引下载走 GitHub API 资产地址，但请求没声明
# Accept: application/octet-stream，GitHub 回的是资产元数据 JSON（1506 字节），
# 解析不出 installer_version，自更新检查静默判定为「已是最新」；同时本机对
# api.github.com 的未认证请求被限流（403）时整条链完全不可达。
#
# 本测试驱动安装器里真实的 Invoke-HubDownload 与自更新代码块（从源码里抽取，
# 不复制粘贴，避免与实现漂移），覆盖：
#   A. 仓库根 raw 通道可用 -> 发现新版本；
#   B. raw 通道不可用 -> 回退 API 资产地址（带 Accept 头）-> 仍发现新版本；
#   C. 反向对照：资产地址只回元数据 JSON 且 CDN 地址不可用 -> 判定无新版
#      （这正是修复前的实际行为，用来证明本测试对缺陷敏感）。
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$installerPath = (Resolve-Path (Join-Path $here ('..' + [IO.Path]::DirectorySeparatorChar + 'Install-WCP-Wordbooks.ps1'))).Path
$installerText = Get-Content -LiteralPath $installerPath -Raw -Encoding UTF8

$pass = 0; $fail = 0
function Check([string]$name, [bool]$cond) {
    if ($cond) { $script:pass++; Write-Host ("  PASS  " + $name) }
    else { $script:fail++; Write-Host ("  FAIL  " + $name) }
}

# --- 从安装器源码抽取真实实现 ---
foreach ($fn in @('Get-PropertyNames', 'Get-FieldOr', 'Format-HubProgressBytes', 'Write-HubProgress', 'Clear-HubProgress', 'Expand-HubZip', 'Invoke-HubDownload')) {
    $m = [regex]::Match($installerText, "(?s)function $fn\(.*?\r?\n\}\r?\n")
    if (-not $m.Success) { throw ('抽取函数失败: ' + $fn) }
    Invoke-Expression $m.Value
}
$script:HubProgressState = @{}
$global:ProgressEvents = @()
function Write-Progress {
    param([string]$Activity, [string]$Status, [int]$PercentComplete, [int]$Id, [switch]$Completed)
    $global:ProgressEvents += [pscustomobject]@{
        Activity = $Activity; Status = $Status; PercentComplete = $PercentComplete
        Id = $Id; Completed = [bool]$Completed
    }
}

Write-HubProgress -Activity 'progress regression' -Current 50 -Total 100 -Id 98
Write-HubProgress -Activity 'progress regression' -Current 100 -Total 100 -Id 98 -Complete
Check '进度 helper 显示中间百分比和 100% 完成' (@($global:ProgressEvents | Where-Object {
    $_.Activity -eq 'progress regression' -and $_.PercentComplete -eq 50
}).Count -gt 0 -and @($global:ProgressEvents | Where-Object {
    $_.Activity -eq 'progress regression' -and $_.PercentComplete -eq 100 -and $_.Status -match '^100%'
}).Count -gt 0 -and @($global:ProgressEvents | Where-Object {
    $_.Activity -eq 'progress regression' -and $_.Completed
}).Count -gt 0)
Check '小文件进度显示字节数而非错误地四舍五入为 0 KB' ((Format-HubProgressBytes 501) -eq '501 B')
$blockStart = $installerText.IndexOf('# ---------- 安装器自更新')
$blockEnd = $installerText.IndexOf('# ---------- 工作目录卫生')
if ($blockStart -lt 0 -or $blockEnd -lt $blockStart) { throw '抽取自更新代码块失败' }
$selfUpdateBlock = $installerText.Substring($blockStart, $blockEnd - $blockStart)
$rawConst = 'https://raw.githubusercontent.com/hanserdesu/WCP-MultiLanguage/main/release-index.json'
Check '自更新代码块含仓库根 raw 索引地址' ($selfUpdateBlock.Contains($rawConst))
Check '索引下载显式声明 octet-stream' ($selfUpdateBlock.Contains("'application/octet-stream'"))
Check '下载函数支持显式 Accept 头' ($selfUpdateBlock.Contains('Invoke-HubDownload') -and
    ((Get-Command Invoke-HubDownload).Parameters.ContainsKey('Accept')))

# --- 本地假 GitHub（TcpListener 手写 HTTP，避开 HttpListener 的 URL ACL） ---
$tempRoot = Join-Path $env:TEMP ('wcp_selfupdate_test_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
$indexFile = Join-Path $tempRoot 'index.json'
$portFile = Join-Path $tempRoot 'port.txt'
$stopFile = Join-Path $tempRoot 'stop.txt'
[IO.File]::WriteAllText($indexFile, (@{
    main_release      = 'hanserdesu/WCP-MultiLanguage'
    installer_version = 'wcp-installer-v9.9.9'
    core_installer    = @{ name = 'x.zip'; size = 1; sha256 = ('a' * 64); url = 'http://127.0.0.1:1/x.zip' }
} | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))

# 真正调用安装器的 ZIP 展开实现，验证内容、覆盖语义和解压进度完成事件。
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipSource = Join-Path $tempRoot 'zip-source'
$zipDest = Join-Path $tempRoot 'zip-dest'
New-Item -ItemType Directory -Path (Join-Path $zipSource 'nested') -Force | Out-Null
$zipPayload = New-Object byte[] (512KB)
for ($i = 0; $i -lt $zipPayload.Length; $i++) { $zipPayload[$i] = [byte]($i % 251) }
[IO.File]::WriteAllBytes((Join-Path $zipSource 'nested\payload.bin'), $zipPayload)
$zipFile = Join-Path $tempRoot 'payload.zip'
[IO.Compression.ZipFile]::CreateFromDirectory($zipSource, $zipFile)
Expand-HubZip $zipFile $zipDest 'progress ZIP test'
Check 'ZIP 展开保留文件内容并报告 100%' (
    (Get-FileHash -LiteralPath (Join-Path $zipDest 'nested\payload.bin') -Algorithm SHA256).Hash -eq
    (Get-FileHash -LiteralPath (Join-Path $zipSource 'nested\payload.bin') -Algorithm SHA256).Hash -and @($global:ProgressEvents | Where-Object {
        $_.Activity -eq 'progress ZIP test' -and $_.PercentComplete -eq 100 -and $_.Status -match '^100%'
    }).Count -gt 0 -and @($global:ProgressEvents | Where-Object {
        $_.Activity -eq 'progress ZIP test' -and $_.Completed
    }).Count -gt 0
)

$serverScript = {
    param($portFile, $indexFile, $stopFile)
    $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    [IO.File]::WriteAllText($portFile, [string]([System.Net.IPEndPoint]$listener.LocalEndpoint).Port)
    $indexBytes = [IO.File]::ReadAllBytes($indexFile)
    $metaBytes = [Text.Encoding]::UTF8.GetBytes('{"url":"https://api.github.com/repos/o/r/releases/assets/1","id":1,"name":"release-index.json","size":501}')
    $missingBytes = [Text.Encoding]::UTF8.GetBytes('{"message":"Not Found"}')
    while (-not (Test-Path -LiteralPath $stopFile)) {
        if (-not $listener.Pending()) { Start-Sleep -Milliseconds 40; continue }
        $client = $listener.AcceptTcpClient()
        try {
            $stream = $client.GetStream()
            $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::ASCII)
            $requestLine = $reader.ReadLine()
            $headers = @{}
            while ($true) {
                $line = $reader.ReadLine()
                if ([string]::IsNullOrEmpty($line)) { break }
                $sep = $line.IndexOf(':')
                if ($sep -gt 0) { $headers[$line.Substring(0, $sep).Trim().ToLowerInvariant()] = $line.Substring($sep + 1).Trim() }
            }
            $path = ($requestLine -split ' ')[1]
            $accept = if ($headers.ContainsKey('accept')) { $headers['accept'] } else { '' }
            $body = $missingBytes
            $status = '404 Not Found'
            if ($path -eq '/raw/release-index.json') { $body = $indexBytes; $status = '200 OK' }
            elseif ($path -eq '/api/asset/1') {
                # 模拟 GitHub 内容协商：带 octet-stream 才给文件本体
                $body = if ($accept -like '*application/octet-stream*') { $indexBytes } else { $metaBytes }
                $status = '200 OK'
            } elseif ($path -eq '/api/legacy/1') {
                # 模拟修复前那条链：无论 Accept 是什么都只回元数据 JSON
                $body = $metaBytes
                $status = '200 OK'
            }
            $head = "HTTP/1.1 $status`r`nContent-Type: application/octet-stream`r`nContent-Length: $($body.Length)`r`nConnection: close`r`n`r`n"
            $headBytes = [Text.Encoding]::ASCII.GetBytes($head)
            $stream.Write($headBytes, 0, $headBytes.Length)
            $stream.Write($body, 0, $body.Length)
            $stream.Flush()
        } finally {
            $client.Close()
        }
    }
    $listener.Stop()
}

$job = Start-Job -ScriptBlock $serverScript -ArgumentList $portFile, $indexFile, $stopFile
$port = $null
for ($i = 0; $i -lt 100 -and -not $port; $i++) {
    Start-Sleep -Milliseconds 100
    if (Test-Path -LiteralPath $portFile) {
        $raw = (Get-Content -LiteralPath $portFile -Raw).Trim()
        if ($raw) { $port = [int]$raw }
    }
}
if (-not $port) { throw '本地假 GitHub 未能在 10 秒内就绪' }
$base = 'http://127.0.0.1:' + $port
Write-Host ("本地假 GitHub: " + $base)

function Invoke-SelfUpdateCheck([string]$rawUrl, [string]$apiUrl, [string]$cdnUrl) {
    $script:promptSeen = $false
    $data = $script:tempRoot
    $Offline = $false
    $Plan = $false
    $List = $false
    function Read-Host { param([string]$Prompt) $script:promptSeen = $true; return 'n' }
    function Get-GitHubJson([string]$url) {
        return [pscustomobject]@{
            tag_name   = 'wcp-mods-v9.9.9'
            created_at = '2099-01-01T00:00:00Z'
            assets     = @([pscustomobject]@{
                name                 = 'release-index.json'
                url                  = $apiUrl
                browser_download_url = $cdnUrl
            })
        }
    }
    $env:WCP_INSTALLER_VERSION = 'wcp-installer-v0.1.2'
    Invoke-Expression $script:selfUpdateBlock.Replace($script:rawConst, $rawUrl)
    return [bool]$script:promptSeen
}

try {
    Check 'A. raw 通道可用时发现新版本' (Invoke-SelfUpdateCheck "$base/raw/release-index.json" "$base/api/asset/1" "$base/cdn/missing.json")
    Check 'B. raw 不可用时回退 API 资产（带 Accept）仍发现新版本' (Invoke-SelfUpdateCheck "$base/raw/missing.json" "$base/api/asset/1" "$base/cdn/missing.json")
    Check 'C. 反向对照：只回元数据 JSON 时判定无新版' (-not (Invoke-SelfUpdateCheck "$base/raw/missing.json" "$base/api/legacy/1" "$base/cdn/missing.json"))
    Check '真实 HTTP 下载路径发出百分比和完成进度' (@($global:ProgressEvents | Where-Object {
        $_.Activity -eq '检查安装器更新' -and $_.PercentComplete -eq 99
    }).Count -gt 0 -and @($global:ProgressEvents | Where-Object {
        $_.Activity -eq '检查安装器更新' -and $_.Completed
    }).Count -gt 0)
} finally {
    [IO.File]::WriteAllText($stopFile, 'stop')
    Start-Sleep -Milliseconds 200
    Stop-Job -Job $job -ErrorAction SilentlyContinue | Out-Null
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue | Out-Null
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item Env:\WCP_INSTALLER_VERSION -ErrorAction SilentlyContinue
}

Write-Host ('结果: {0} 通过, {1} 失败' -f $pass, $fail)
if ($fail -gt 0) { exit 1 } else { exit 0 }
