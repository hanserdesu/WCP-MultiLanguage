param(
    [string]$HostLabel = 'Windows PowerShell'
)

$ErrorActionPreference = 'Stop'

# 每次发布安装包时同步更新，失败反馈里会带上这个版本号。
$InstallerVersion = 'wcp-jp-v1.2.9.1'
$IssueBaseUrl = 'https://github.com/hanserdesu/japanese/issues/new'

$version = $PSVersionTable.PSVersion.ToString()
Write-Host "运行环境：$HostLabel $version" -ForegroundColor DarkCyan
# 把安装器版本传给主脚本，供自更新检查比对（老版本没有这一步，等于跳过检查）。
$env:WCP_INSTALLER_VERSION = $InstallerVersion
$installScript = Join-Path $PSScriptRoot 'Install-WCP-Japanese.ps1'
$success = $false
$failureDetail = ''

try {
    & $installScript
    $success = $true
} catch {
    Write-Host ''
    # GetAwaiter().GetResult() 这类调用会把真实原因包在 AggregateException
    # 的内层异常里，只显示最外层只会得到「发生一个或多个错误」。
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

    # 自动反馈：把错误链与日志尾部整理成预填好的 GitHub Issue，直接打开
    # 浏览器，群友核对后点一下 Submit 即可；无需任何账号配置。
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
        # Issue 标题取最内层错误；URL 长度做硬限制，防止浏览器拒绝。
        $titleLines = $failureDetail -split "`n"
        $innermost = $titleLines[$titleLines.Count - 1]
        if ($innermost.Length -gt 80) { $innermost = $innermost.Substring(0, 80) }
        if ($bodyText.Length -gt 4000) { $bodyText = $bodyText.Substring(0, 4000) }
        $issueUrl = $IssueBaseUrl + '?title=' + [Uri]::EscapeDataString('安装失败：' + $innermost) +
            '&body=' + [Uri]::EscapeDataString($bodyText)
        Write-Host ''
        Write-Host '正在打开浏览器为你预填错误反馈 Issue（打开后点击 Submit 即可提交）...' -ForegroundColor Cyan
        Start-Process $issueUrl
        Write-Host '若浏览器没有打开，也可以手动访问：' -ForegroundColor DarkYellow
        Write-Host $IssueBaseUrl -ForegroundColor DarkYellow
        Write-Host "并粘贴这个文件的内容：$logPath" -ForegroundColor DarkYellow
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
Write-Host '窗口将保持打开，请点击右上角 X 关闭；按 Enter 不会关闭窗口。' -ForegroundColor Yellow
