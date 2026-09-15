# Installer extractor + v1.2.5 cleanup regression (Windows PowerShell 5.1+).
# 用法: powershell -File work/tmp/installer_regression.ps1 [音频zip路径]
# 不传 zip 时使用 output/release/wcp-japanese-audio-words.zip；缺失则跳过解压用例。
# 必须带 UTF-8 BOM 保存（PS 5.1 对无 BOM 文件按 ANSI 解析，中文会炸语法）。
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$installerPath = Join-Path $repoRoot 'wcp_wordbooks\installer\Install-WCP-Japanese.ps1'
$text = Get-Content -LiteralPath $installerPath -Raw -Encoding UTF8

# 按安装器的真实加载方式抽取解压器与辅助函数
$start = $text.IndexOf('function Ensure-ZipExtractor')
$end = $text.IndexOf('function Get-InstallerErrorLogPath')
$block = $text.Substring($start, $end - $start)
$block = $block -replace 'if \(''WcpJapaneseZipSession'' -as \[type\]\) \{ return \}', ''
Invoke-Expression $block
foreach ($fnName in @('Write-Step','Get-Sha256','Copy-TreeNet','Get-ExtendedPath','Remove-TreeNet','Get-InstallerErrorLogPath','Write-InstallerErrorLog','Show-ExtractFailure','Expand-ZipWithProgress','Backup-PackWithoutAudio','Remove-LegacyRedundancy')) {
    $s = $text.IndexOf("function $fnName")
    if ($s -ge 0) {
        $after = $text.IndexOf("`nfunction ", $s + 10)
        if ($after -lt 0) { $after = $text.Length }
        Invoke-Expression $text.Substring($s, $after - $s)
    }
}
Write-Host ('PowerShell ' + $PSVersionTable.PSVersion.ToString())
$stage = Join-Path $env:TEMP ('wcp-inst-regression-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$fail = 0

# --- T1: 真实音频包完整解压 ---
$audioZip = if ($args.Count -gt 0) { $args[0] } else { Join-Path $repoRoot 'wcp_wordbooks\output\release\wcp-japanese-audio-words.zip' }
if (Test-Path -LiteralPath $audioZip) {
    $dest1 = Join-Path $stage 'out1'
    try {
        Expand-ZipWithProgress $audioZip $dest1 '单词音频'
        $n = [IO.Directory]::GetFiles($dest1, '*', [IO.SearchOption]::AllDirectories).Count
        Write-Host "T1 PASS ($n files extracted)"
    } catch { Write-Host "T1 FAIL: $($_.Exception.Message)"; $fail = 1 }
} else {
    Write-Host 'T1 SKIP (audio zip not found)'
}

# --- T2: 备份跳过 audio 子树 ---
$packSrc = Join-Path $stage 'packsrc'
New-Item -ItemType Directory -Force -Path (Join-Path $packSrc 'audio\word') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packSrc 'db') | Out-Null
[IO.File]::WriteAllText((Join-Path $packSrc 'manifest.json'), '{"k":1}')
[IO.File]::WriteAllBytes((Join-Path $packSrc 'audio\word\a.mp3'), (New-Object byte[] 100))
[IO.File]::WriteAllBytes((Join-Path $packSrc 'db\m.sqlite'), (New-Object byte[] 100))
Backup-PackWithoutAudio $packSrc (Join-Path $stage 'packbak')
$bk = Join-Path $stage 'packbak'
if ((-not (Test-Path -LiteralPath (Join-Path $bk 'audio'))) -and
    (Test-Path -LiteralPath (Join-Path $bk 'manifest.json')) -and
    (Test-Path -LiteralPath (Join-Path $bk 'db\m.sqlite'))) {
    Write-Host 'T2 PASS (audio skipped, rest copied)'
} else { Write-Host 'T2 FAIL'; $fail = 1 }

# --- T3: 冗余清理保留当前哈希缓存 + 最近 3 份备份 ---
$dls = Join-Path $stage 'wcp\jpmod_downloads'
New-Item -ItemType Directory -Force -Path $dls | Out-Null
$curWord = Join-Path $dls 'wcp-japanese-audio-words.zip'
$curSent = Join-Path $dls 'wcp-japanese-audio-sentences.zip'
[IO.File]::WriteAllBytes($curWord, (New-Object byte[] 10))
[IO.File]::WriteAllBytes($curSent, (New-Object byte[] 10))
$h1 = (Get-FileHash -LiteralPath $curWord -Algorithm SHA256).Hash.ToLower()
$h2 = (Get-FileHash -LiteralPath $curSent -Algorithm SHA256).Hash.ToLower()
[IO.File]::WriteAllBytes((Join-Path $dls 'wcp-japanese-audio-words.zip.download'), (New-Object byte[] 500000))
[IO.File]::WriteAllBytes((Join-Path $dls 'wcp-japanese-audio-words.zip.001'), (New-Object byte[] 300000))
$broot = Join-Path $stage 'wcp\jpmod_backups'
foreach ($t in @('20260901_000000','20260902_000000','20260903_000000','20260904_000000','20260905_000000')) {
    $d = Join-Path $broot $t
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $d 'x.bin'), (New-Object byte[] 200000))
}
Remove-LegacyRedundancy -DataDir (Join-Path $stage 'wcp') `
    -WordAsset ([pscustomobject]@{ name = 'wcp-japanese-audio-words.zip'; sha256 = $h1 }) `
    -SentenceAsset ([pscustomobject]@{ name = 'wcp-japanese-audio-sentences.zip'; sha256 = $h2 })
$names = @(Get-ChildItem -LiteralPath $dls -File | ForEach-Object Name | Sort-Object)
$leftBackups = @(Get-ChildItem -LiteralPath $broot -Directory)
if ($names.Count -eq 2 -and $names -contains 'wcp-japanese-audio-words.zip' -and
    $names -contains 'wcp-japanese-audio-sentences.zip' -and $leftBackups.Count -eq 3) {
    Write-Host 'T3 PASS (stale cache/parts removed; kept 2 current zips + 3 newest backups)'
} else {
    Write-Host ("T3 FAIL: downloads = " + ($names -join ',') + " ; backups = " + $leftBackups.Count); $fail = 1
}

Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
if ($fail -eq 0) { Write-Host 'INSTALLER REGRESSION PASS' } else { Write-Host 'INSTALLER REGRESSION FAILED'; exit 1 }
