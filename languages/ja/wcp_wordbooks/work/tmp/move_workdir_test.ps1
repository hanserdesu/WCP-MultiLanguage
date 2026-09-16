# 用临时目录验证安装器里 Move-LegacyWorkDir 的行为（从安装器源码提取函数体，保证测的是同一份实现）
$ErrorActionPreference = 'Stop'

$src = Get-Content -LiteralPath 'D:\ATooManyLanguage\Japanese\wcp_wordbooks\installer\Install-WCP-Japanese.ps1' -Raw -Encoding UTF8
$startMarker = "function Move-LegacyWorkDir {"
$endMarker = "function Remove-LegacyRedundancy {"
$start = $src.IndexOf($startMarker)
$end = $src.IndexOf($endMarker, $start)
if ($start -lt 0 -or $end -lt 0) { throw '无法从安装器提取 Move-LegacyWorkDir 函数' }
$funcText = $src.Substring($start, $end - $start)
Invoke-Expression $funcText

$root = Join-Path $env:TEMP ('wcp-move-test-' + [guid]::NewGuid().ToString('N'))
$wcp = Join-Path $root 'wcp'
$work = Join-Path $root 'jpmod_data'
New-Item -ItemType Directory -Path (Join-Path $wcp 'jpmod_downloads') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $wcp 'jpmod_backups\20260901_000000') -Force | Out-Null
[IO.File]::WriteAllBytes((Join-Path $wcp 'jpmod_downloads\a.zip'), [byte[]](1..8))
[IO.File]::WriteAllBytes((Join-Path $wcp 'jpmod_backups\20260901_000000\SaveFile.es3'), [byte[]](9..16))

$pass = 0; $fail = 0
function Check([string]$name, [bool]$cond) {
    if ($cond) { $script:pass++; Write-Host ("  PASS  " + $name) }
    else { $script:fail++; Write-Host ("  FAIL  " + $name) }
}

# T1: 首次迁移（目标不存在 → 整体 Move）
Write-Host ("DEBUG 旧存在=" + (Test-Path -LiteralPath (Join-Path $wcp 'jpmod_downloads')) + " work存在=" + (Test-Path -LiteralPath $work) + " 新存在=" + (Test-Path -LiteralPath (Join-Path $work 'downloads')))
Write-Host ("DEBUG 函数已定义=" + [bool](Get-Command Move-LegacyWorkDir -ErrorAction SilentlyContinue))
Move-LegacyWorkDir -Old (Join-Path $wcp 'jpmod_downloads') -New (Join-Path $work 'downloads')
Write-Host ("DEBUG after: 旧存在=" + (Test-Path -LiteralPath (Join-Path $wcp 'jpmod_downloads')) + " 新存在=" + (Test-Path -LiteralPath (Join-Path $work 'downloads')))
Check 'T1 旧位置已搬空' (-not (Test-Path -LiteralPath (Join-Path $wcp 'jpmod_downloads')))
Check 'T1 新位置有文件' ((Test-Path -LiteralPath (Join-Path $work 'downloads\a.zip')))

# T2: 目标已存在 → 只搬缺失项
Write-Host ("DEBUG T2前: wcp存在=" + (Test-Path -LiteralPath $wcp) + " 旧目录存在=" + (Test-Path -LiteralPath (Join-Path $wcp 'jpmod_downloads')))
$mk = New-Item -ItemType Directory -Path (Join-Path $wcp 'jpmod_downloads') -Force -ErrorAction Continue
Write-Host ("DEBUG T2后: 旧目录存在=" + (Test-Path -LiteralPath (Join-Path $wcp 'jpmod_downloads')) + " mk=" + ($mk -ne $null))
[IO.File]::WriteAllBytes((Join-Path $wcp 'jpmod_downloads\b.zip'), [byte[]](1..4))
[IO.File]::WriteAllBytes((Join-Path $wcp 'jpmod_downloads\a.zip'), [byte[]](99))   # 同名旧文件：不应覆盖
Move-LegacyWorkDir -Old (Join-Path $wcp 'jpmod_downloads') -New (Join-Path $work 'downloads')
Check 'T2 缺失项已补搬' ((Test-Path -LiteralPath (Join-Path $work 'downloads\b.zip')))
Check 'T2 不覆盖同名新文件' ((Get-Item -LiteralPath (Join-Path $work 'downloads\a.zip')).Length -eq 8)

# T3: 旧位置不存在 → 静默返回
Move-LegacyWorkDir -Old (Join-Path $wcp 'no_such_dir') -New (Join-Path $work 'x')
Check 'T3 无旧目录时不报错' $true

# T4: 备份目录整搬
Move-LegacyWorkDir -Old (Join-Path $wcp 'jpmod_backups') -New (Join-Path $work 'backups')
Check 'T4 备份新位置有内容' (Test-Path -LiteralPath (Join-Path $work 'backups\20260901_000000\SaveFile.es3'))

Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ''
Write-Host ("结果: {0} 通过, {1} 失败" -f $pass, $fail)
if ($fail -gt 0) { exit 1 } else { exit 0 }
