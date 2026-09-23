# MultiLanguage 安装器启动器（学习 ja 一键包 run-installer.ps1 的实战经验）。
#
# 职责：
#   1. 注入安装器版本号（自更新检查的比对基准；直接运行主脚本则无版本号、跳过检查）。
#   2. 异常链完整展开（GetAwaiter().GetResult() 会把真实原因包在 AggregateException 内层，
#      只打印最外层只会得到「发生一个或多个错误」）。
#   3. 失败时预填 GitHub Issue（错误链 + 日志尾部自动带上，群友点 Submit 即可）。
#   4. 结束后窗口保持打开（双击运行时 cmd 窗口不会一闪而过）。
#
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File run-installer.ps1
#       （或由 打包安装器.py 生成的一键 cmd 调起）

param(
    [string]$HostLabel = 'Windows PowerShell',
    # 双击入口「更新词书资源.cmd」走 -Update；其余参数透传给主脚本。
    [switch]$Update,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs = @()
)

$ErrorActionPreference = 'Stop'

# 每次发布安装包时同步更新（由 打包安装器.py 维护），失败反馈里会带上这个版本号。
$InstallerVersion = 'wcp-installer-v0.1.8'
$IssueBaseUrl = 'https://github.com/hanserdesu/WCP-MultiLanguage/issues/new'

$version = $PSVersionTable.PSVersion.ToString()
Write-Host "运行环境：$HostLabel $version" -ForegroundColor DarkCyan
# 把安装器版本传给主脚本，供自更新检查比对（老版本没有这一步，等于跳过检查）。
$env:WCP_INSTALLER_VERSION = $InstallerVersion
$installScript = Join-Path $PSScriptRoot 'Install-WCP-Wordbooks.ps1'
$success = $false
$failureDetail = ''
$installArgs = @()
if ($Update) { $installArgs += '-Update' }
if ($ExtraArgs) { $installArgs += $ExtraArgs }

try {
    & $installScript @installArgs
    $success = $true
} catch {
    Write-Host ''
    $ex = $_.Exception
    $depth = 0
    $chain = @()
    while ($ex -and $depth -lt 6) {
        Write-Host $ex.Message -ForegroundColor Red
        $chain += $ex.GetType().Name + ': ' + $ex.Message
        if (-not $ex.InnerException) { break }
        $ex = $ex.InnerException
        $depth++
    }
    if ($ex -and $chain.Count -gt 0 -and $chain[-1] -ne ($ex.GetType().Name + ': ' + $ex.Message)) {
        Write-Host $ex.Message -ForegroundColor Red
        $chain += $ex.GetType().Name + ': ' + $ex.Message
    }
    $failureDetail = [string]::Join("`n", $chain)
    Write-Host '安装没有完成。请保留此窗口中的错误信息，便于排查。' -ForegroundColor Yellow
    $logPath = Join-Path $env:USERPROFILE 'AppData\LocalLow\WCP\wcp\installer-error.log'
    if (Test-Path -LiteralPath $logPath) {
        Write-Host "更多详情已记录在：$logPath" -ForegroundColor DarkYellow
    }

    # 自动反馈：错误链与日志尾部整理成预填好的 GitHub Issue，打开浏览器即可提交。
    try {
        $bodyLines = @()
        $bodyLines += '### 安装器反馈（自动生成，请补充发生了什么）'
        $bodyLines += ''
        $bodyLines += '- 安装器版本：' + $InstallerVersion
        $bodyLines += '- 运行环境：' + $HostLabel + ' ' + $PSVersionTable.PSVersion.ToString()
        $bodyLines += '- 操作系统：' + [Environment]::OSVersion.VersionString
        $bodyLines += '- 时间：' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        $bodyLines += ''
        $bodyLines += '### 错误链（由外到内）'
        $bodyLines += '```'
        $bodyLines += $failureDetail
        $bodyLines += '```'
        if (Test-Path -LiteralPath $logPath) {
            $tail = @(Get-Content -LiteralPath $logPath -Tail 40 -Encoding UTF8 -ErrorAction SilentlyContinue)
            if ($tail.Count -gt 0) {
                $bodyLines += ''
                $bodyLines += '### installer-error.log 尾部'
                $bodyLines += '```'
                $bodyLines += $tail
                $bodyLines += '```'
            }
        }
        $bodyText = [string]::Join("`r`n", $bodyLines)
        $titleLines = $failureDetail -split "`n"
        $innermost = $titleLines[$titleLines.Count - 1]
        if ($innermost.Length -gt 80) { $innermost = $innermost.Substring(0, 80) }
        if ($bodyText.Length -gt 4000) { $bodyText = $bodyText.Substring(0, 4000) }
        $issueUrl = $IssueBaseUrl + '?title=' + [Uri]::EscapeDataString('安装失败：' + $innermost) +
            '&body=' + [Uri]::EscapeDataString($bodyText)
        Write-Host ''
        Write-Host '正在打开浏览器为你预填错误反馈 Issue（打开后点击 Submit 即可提交）...' -ForegroundColor Cyan
        Start-Process $issueUrl
        Write-Host '若浏览器没有打开，也可以手动把上面的错误信息发给作者。' -ForegroundColor DarkYellow
    } catch {
        Write-Host '自动打开反馈页面失败，请手动把上面的错误信息发给作者。' -ForegroundColor DarkYellow
    }
}

Write-Host ''
if ($success) {
    Write-Host '安装成功。请重新启动万词破。' -ForegroundColor Green
} else {
    Write-Host '安装失败。' -ForegroundColor Red
}
# 只有经 --keep-open 双击入口启动时窗口才真的会留着；直接跑脚本时不能乱承诺。
if ($env:WCP_KEEP_OPEN -eq '1') {
    Write-Host '窗口将保持打开，请点击右上角 X 关闭；按 Enter 不会关闭窗口。' -ForegroundColor Yellow
} else {
    Write-Host '脚本执行结束（直接运行本脚本时窗口由你所在的终端决定是否保留）。' -ForegroundColor DarkGray
}
