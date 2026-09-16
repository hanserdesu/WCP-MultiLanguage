# -*- coding: utf-8 -*-
"""把安装器的工作文件（下载缓存/备份/解压临时目录）移出 Steam 云同步范围。

改动 Install-WCP-Japanese.ps1（CRLF 文件，处理时统一为 LF 再写回）：
  1. 新增 $workRoot = <LocalLow>\\WCP\\jpmod_data（packs 同级，不在云同步范围内）
  2. 首次运行时把旧位置（wcp\\jpmod_downloads / wcp\\jpmod_backups）同盘搬出来
  3. 缓存/备份/解压临时目录/自更新下载全部改用 $workRoot
  4. C# 存档修复 helper 增加 backupRoot 参数（默认兼容旧行为）
  5. 相关提示文案同步

逐条替换并打印匹配数；任何一条不匹配即整体放弃（不写入）。
"""
from pathlib import Path

P = Path(r'D:/ATooManyLanguage/Japanese/wcp_wordbooks/installer/Install-WCP-Japanese.ps1')
raw = P.read_bytes()
had_bom = raw[:3] == b'\xef\xbb\xbf'
body = raw[3:] if had_bom else raw
probe = body.replace(b'\r\n', b'')
if b'\n' in probe:
    print('警告：文件存在裸 LF 行尾，仍按 CRLF 归一化处理')
src = body.decode('utf-8').replace('\r\n', '\n')

R = []  # (old, new, 期望匹配数)

# ── 1) 变量区：新增 workRoot + 迁移调用 + 备份指向新位置 ─────────────────
R.append((
    """$data = Join-Path $wcpRoot 'wcp'
$packsPayload = Join-Path $payload 'packs'
$packsRoot = Join-Path $wcpRoot 'packs'
New-Item -ItemType Directory -Force -Path $data | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $data "jpmod_backups\\$stamp"
""",
    """$data = Join-Path $wcpRoot 'wcp'
$packsPayload = Join-Path $payload 'packs'
$packsRoot = Join-Path $wcpRoot 'packs'
# 工作文件（下载缓存/备份/解压临时目录）刻意放在 wcp 目录之外：
#   Steam 对该游戏的云同步范围是整个 %USERPROFILE%\\AppData\\LocalLow\\WCP\\wcp，
#   这些没有同步价值的大文件（下载缓存约 1.6GB、解压临时目录数 GB）会把云同步
#   配额/队列撑爆，导致 MyBook.es3 等关键存档永远排不进同步队列（2026-09-16 实测
#   该目录 53 万文件 / 约 15GB，Steam 云状态长期显示「无法同步」）。
#   jpmod_data 与 packs 同级，不在云同步范围内。
$workRoot = Join-Path $wcpRoot 'jpmod_data'
New-Item -ItemType Directory -Force -Path $data | Out-Null
New-Item -ItemType Directory -Force -Path $workRoot | Out-Null
Move-LegacyWorkDir -Old (Join-Path $data 'jpmod_downloads') -New (Join-Path $workRoot 'downloads')
Move-LegacyWorkDir -Old (Join-Path $data 'jpmod_backups') -New (Join-Path $workRoot 'backups')
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $workRoot "backups\\$stamp"
""",
    1,
))

# ── 2) 迁移函数（插在 Remove-LegacyRedundancy 之前）────────────────────
R.append((
    "function Remove-LegacyRedundancy {",
    """function Move-LegacyWorkDir {
    # 把旧版本放在 wcp 目录（Steam 云同步范围内）的工作目录搬到范围之外。
    # 同盘 Move 是瞬间重命名，不会触发重新下载 1.6GB 缓存；新位置已存在时
    # 只搬运缺失项；任何失败都只提示，绝不影响安装。
    param(
        [Parameter(Mandatory = $true)][string]$Old,
        [Parameter(Mandatory = $true)][string]$New
    )
    if (-not (Test-Path -LiteralPath $Old)) { return }
    try {
        if (-not (Test-Path -LiteralPath $New)) {
            Move-Item -LiteralPath $Old -Destination $New -Force -ErrorAction Stop
            Write-Host ("已把 {0} 移出 Steam 云同步范围：{1}" -f (Split-Path -Leaf $Old), $New) -ForegroundColor DarkGray
            return
        }
        $moved = 0
        foreach ($item in @(Get-ChildItem -LiteralPath $Old -Force -ErrorAction SilentlyContinue)) {
            $target = Join-Path $New $item.Name
            if (Test-Path -LiteralPath $target) { continue }
            try {
                Move-Item -LiteralPath $item.FullName -Destination $target -Force -ErrorAction Stop
                $moved++
            } catch { }
        }
        if ($moved -gt 0) {
            Write-Host ("已把 {0} 项移出 Steam 云同步范围：{1}" -f $moved, $New) -ForegroundColor DarkGray
        }
    } catch {
        Write-Host ("工作目录迁移失败（不影响安装，后续使用新位置）：{0}" -f $_.Exception.Message) -ForegroundColor DarkYellow
    }
}

function Remove-LegacyRedundancy {""",
    1,
))

# ── 3) Remove-LegacyRedundancy：参数与内部路径改指 workRoot ─────────────
R.append((
    """    param(
        [string]$DataDir,
        $WordAsset,
        $SentenceAsset
    )""",
    """    param(
        [string]$WorkRoot,
        $WordAsset,
        $SentenceAsset
    )""",
    1,
))
R.append((
    "$downloads = Join-Path $DataDir 'jpmod_downloads'",
    "$downloads = Join-Path $WorkRoot 'downloads'",
    1,
))
R.append((
    "$backupRoot = Join-Path $DataDir 'jpmod_backups'",
    "$backupRoot = Join-Path $WorkRoot 'backups'",
    1,
))
R.append((
    "Remove-LegacyRedundancy -DataDir $data -WordAsset $wordAsset -SentenceAsset $sentenceAsset",
    "Remove-LegacyRedundancy -WorkRoot $workRoot -WordAsset $wordAsset -SentenceAsset $sentenceAsset",
    1,
))

# ── 4) 下载缓存目录 ────────────────────────────────────────────────────
R.append((
    "$downloadDir = Join-Path $data 'jpmod_downloads'",
    "$downloadDir = Join-Path $workRoot 'downloads'",
    1,
))

# ── 5) 解压临时目录：扫新位置 + 清理旧位置残留 ─────────────────────────
R.append((
    """$stagePattern = 'jpmod_audio_stage*'
foreach ($staleStage in @(Get-ChildItem -LiteralPath $data -Directory -Filter $stagePattern -ErrorAction SilentlyContinue)) {""",
    """$stagePattern = 'audio_stage*'
# 旧版本把解压临时目录放在 wcp 里（云同步范围内），顺带清掉残留。
foreach ($legacyStage in @(Get-ChildItem -LiteralPath $data -Directory -Filter 'jpmod_audio_stage*' -ErrorAction SilentlyContinue)) {
    try {
        Remove-TreeNet $legacyStage.FullName
        Write-Host "已清理旧位置的临时目录：$($legacyStage.Name)" -ForegroundColor DarkGray
    } catch { }
}
foreach ($staleStage in @(Get-ChildItem -LiteralPath $workRoot -Directory -Filter $stagePattern -ErrorAction SilentlyContinue)) {""",
    1,
))
R.append((
    """$audioStage = Join-Path $data ("jpmod_audio_stage_{0}_{1}" -f $stamp, ([guid]::NewGuid().ToString('N')))""",
    """$audioStage = Join-Path $workRoot ("audio_stage_{0}_{1}" -f $stamp, ([guid]::NewGuid().ToString('N')))""",
    1,
))

# ── 6) 自更新：下载/临时文件也放 workRoot ─────────────────────────────
R.append((
    "$idxTmp = Join-Path $data 'release-index.json.check'",
    "$idxTmp = Join-Path $workRoot 'release-index.json.check'",
    1,
))
R.append((
    "$coreTmp = Join-Path $data $coreName",
    "$coreTmp = Join-Path $workRoot $coreName",
    1,
))
R.append((
    '$newPkgDir = Join-Path $data "installer_update_$stamp"',
    '$newPkgDir = Join-Path $workRoot "installer_update_$stamp"',
    1,
))

# ── 7) 文案：缓存路径提示 ────────────────────────────────────────────
R.append((
    "请删除 %USERPROFILE%\\AppData\\LocalLow\\WCP\\wcp\\jpmod_downloads 目录后重试。",
    "请删除 %USERPROFILE%\\AppData\\LocalLow\\WCP\\jpmod_data\\downloads 目录后重试。",
    1,
))
R.append((
    "缓存位置：$data\\jpmod_downloads",
    "缓存位置：$workRoot\\downloads",
    1,
))

# ── 8) C# helper：备份根可参数化（默认保持旧行为）──────────────────────
R.append((
    """    public static string FindBestSaveBackup(string dataDir)
    {
        var candidates = new List<string>();
        string jpmodDir = Path.Combine(dataDir, "jpmod_backups");""",
    """    public static string FindBestSaveBackup(string dataDir, string backupRoot)
    {
        var candidates = new List<string>();
        string jpmodDir = string.IsNullOrEmpty(backupRoot) ? Path.Combine(dataDir, "jpmod_backups") : backupRoot;""",
    1,
))
R.append((
    """    public static bool TryRepairSaveFile(string savePath, string dataDir, out string restoredFrom)
    {
        restoredFrom = null;
        if (!IsSaveCorrupted(savePath)) return false;
        string best = FindBestSaveBackup(dataDir);""",
    """    public static bool TryRepairSaveFile(string savePath, string dataDir, string backupRoot, out string restoredFrom)
    {
        restoredFrom = null;
        if (!IsSaveCorrupted(savePath)) return false;
        string best = FindBestSaveBackup(dataDir, backupRoot);""",
    1,
))
R.append((
    """    public static bool TryRepairMyBook(string myBookPath, string dataDir, out string restoredFrom)""",
    """    public static bool TryRepairMyBook(string myBookPath, string dataDir, string backupRoot, out string restoredFrom)""",
    1,
))
R.append((
    """            string jpmodDir = Path.Combine(dataDir, "jpmod_backups");""",
    """            string jpmodDir = string.IsNullOrEmpty(backupRoot) ? Path.Combine(dataDir, "jpmod_backups") : backupRoot;""",
    1,
))

# ── 9) PS 调用点：传入备份根 ─────────────────────────────────────────
R.append((
    "if ([WcpEs3Helper]::TryRepairSaveFile($savePath, $data, [ref]$repairedSave)) {",
    "if ([WcpEs3Helper]::TryRepairSaveFile($savePath, $data, (Join-Path $workRoot 'backups'), [ref]$repairedSave)) {",
    1,
))
R.append((
    "if ([WcpEs3Helper]::TryRepairMyBook($myBookPath, $data, [ref]$repairedMb)) {",
    "if ([WcpEs3Helper]::TryRepairMyBook($myBookPath, $data, (Join-Path $workRoot 'backups'), [ref]$repairedMb)) {",
    1,
))

ok = True
for old, new, want in R:
    n = src.count(old)
    if n != want:
        ok = False
        print('X 匹配 %d 次（期望 %d）：%s' % (n, want, old.splitlines()[0][:70]))
    else:
        src = src.replace(old, new)
        print('OK %s' % old.splitlines()[0][:70])

if not ok:
    print('有替换未命中，未写入任何改动。')
    raise SystemExit(1)

out_text = src.replace('\n', '\r\n')
out = out_text.encode('utf-8')
if had_bom:
    out = b'\xef\xbb\xbf' + out
P.write_bytes(out)
print('已写入 %s（%d 字节，BOM=%s）' % (P, len(out), out[:3] == b'\xef\xbb\xbf'))
