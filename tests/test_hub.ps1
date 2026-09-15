# Offline unit tests for WordbookHub.psm1 — no network, no game dir writes.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module (Join-Path $here '..\WordbookHub.psm1') -Force

$pass = 0; $fail = 0
function Check([string]$name, [bool]$cond) {
    if ($cond) { $script:pass++; Write-Host ("  PASS  " + $name) }
    else { $script:fail++; Write-Host ("  FAIL  " + $name) }
}

# --- fixture ---
$catJson = @'
{
  "schema": 1,
  "wordbooks": [
    { "id": "a", "language": "xx", "display_name": "A", "repo": "r/a", "version": "v1",
      "word_count": 10, "es3_prefix": "xx",
      "disk": { "extract_mb": 100 },
      "assets": [ { "kind": "word_audio", "name": "a1.zip", "size": 52428800, "sha256": "1111111111111111111111111111111111111111111111111111111111111111" } ] },
    { "id": "b", "language": "yy", "display_name": "B", "repo": "r/b", "version": "v2",
      "word_count": 20, "es3_prefix": "yy",
      "disk": { "extract_mb": 200 },
      "assets": [ { "kind": "word_audio", "name": "b1.zip", "size": 104857600, "sha256": "2222222222222222222222222222222222222222222222222222222222222222" } ] }
  ]
}
'@
$cat = $catJson | ConvertFrom-Json

# catalog validation
Assert-WordbookCatalog -Catalog $cat
Check 'catalog 有效' $true
try { $bad = $catJson -replace '"schema": 1', '"no_schema": 1' | ConvertFrom-Json; Assert-WordbookCatalog -Catalog $bad; Check '缺 schema 拒绝' $false }
catch { Check '缺 schema 拒绝' ($_.Exception.Message -match '缺少字段') }

# 随包目录：在线发现按词书 id 建索引，repo 只是每行资产 URL 的宿主记录；同一仓库
# 承载多本词书没有问题，但每行资产必须真的发布在该 repo 名下，防止 404 死链。
$shipped = Get-Content -LiteralPath (Join-Path $here '..\catalog.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Assert-WordbookCatalog -Catalog $shipped
Check '随包目录有效' $true
$shipIds = @($shipped.wordbooks | ForEach-Object { [string]$_.id })
Check '词书 id 两两不同' (@($shipIds | Sort-Object -Unique).Count -eq $shipIds.Count)
Check '词书资产 URL 宿主与 repo 一致' (@(
    $shipped.wordbooks | Where-Object {
        $repoTail = ([string]$_.repo -split '/')[-1]
        @($_.assets | Where-Object { ([string]$_.url -split '/')[4] -eq $repoTail }).Count -eq @($_.assets).Count
    }
).Count -eq $shipIds.Count)
$available = @($shipped.wordbooks | Where-Object { [string]$_.status -eq 'available' })
$fullyLinked = @($available | Where-Object {
    $assets = @($_.assets)
    $assets.Count -gt 0 -and @($assets | Where-Object {
        $_.url -match '^https://github\.com/.+/releases/download/.+/.+$' -and
        $_.size -gt 0 -and $_.sha256 -match '^[0-9a-f]{64}$'
    }).Count -eq $assets.Count
})
Check 'available 词书每项都是可校验的 release 资产' ($available.Count -eq $fullyLinked.Count)

# selection
$sel = @(Resolve-WordbookSelection -Catalog $cat -Ids @('b'))
Check '按 id 选择' ($sel.Count -eq 1 -and $sel[0].id -eq 'b')
$selAll = @(Resolve-WordbookSelection -Catalog $cat -All)
Check '全选' ($selAll.Count -eq 2)
try { Resolve-WordbookSelection -Catalog $cat -Ids @('zzz') | Out-Null; Check '未知 id 拒绝' $false }
catch { Check '未知 id 拒绝' ($_.Exception.Message -match '没有词书') }

# diff: nothing installed
$diffEmpty = @(Get-WordbookAssetDiff -Wordbook $cat.wordbooks[0] -InstalledState $null)
Check '未安装 = 全部需要下载' ($diffEmpty.Count -eq 1)

# diff: installed same sha
$inst = [pscustomobject]@{ a = [pscustomobject]@{ version='v1'; files=[pscustomobject]@{ 'a1.zip'=[pscustomobject]@{ sha256='1111111111111111111111111111111111111111111111111111111111111111' } } } }
$diffSame = @(Get-WordbookAssetDiff -Wordbook $cat.wordbooks[0] -InstalledState $inst)
Check '已安装同哈希 = 无需下载' ($diffSame.Count -eq 0)

# diff: installed different sha
$instOld = [pscustomobject]@{ a = [pscustomobject]@{ version='v0'; files=[pscustomobject]@{ 'a1.zip'=[pscustomobject]@{ sha256='9999999999999999999999999999999999999999999999999999999999999999' } } } }
$diffOld = @(Get-WordbookAssetDiff -Wordbook $cat.wordbooks[0] -InstalledState $instOld)
Check '已安装旧哈希 = 需要更新' ($diffOld.Count -eq 1)

# installed fully
Check '完整安装判定' (Test-WordbookInstalledFully -Wordbook $cat.wordbooks[0] -InstalledState $inst)
Check '旧版本不算完整安装' (-not (Test-WordbookInstalledFully -Wordbook $cat.wordbooks[0] -InstalledState $instOld))

# disk plan: fresh install both
$plan = New-DiskPlan -Wordbooks (Resolve-WordbookSelection -Catalog $cat -All) -InstalledState $null
Check 'fresh 峰值 = 下载 + 解压' ($plan.peak_mb -eq 450.0)
Check 'fresh 最终 = 解压' ($plan.final_mb -eq 300.0)

# disk plan: fully installed
$planHave = New-DiskPlan -Wordbooks @($cat.wordbooks[0]) -InstalledState $inst
Check '已安装 = 0 下载 0 解压' ($planHave.peak_mb -eq 0.0 -and $planHave.final_mb -eq 0.0)

# disk plan: partially installed (b new, a old)
$planMix = New-DiskPlan -Wordbooks (Resolve-WordbookSelection -Catalog $cat -All) -InstalledState $instOld
Check '混合: a 需更新 + b 新装' ($planMix.peak_mb -eq 450.0)

# compatibility
$c1 = Test-DiskPlanCompatibility -Plan $plan -FreeMb 1000
Check '充足' $c1.ok
$c2 = Test-DiskPlanCompatibility -Plan $plan -FreeMb 200
Check '不足' (-not $c2.ok)
Check '不足差额' ($c2.shortfall_mb -eq 762.0)

# installer contract: a slot manifest is copied to the host-owned seed path
$installerText = Get-Content -LiteralPath (Join-Path $here '..\Install-WCP-Wordbooks.ps1') -Raw -Encoding UTF8
Check 'slot manifest 写入 host seed' ($installerText -match "asset\.kind -eq 'slot_manifest'" -and
    $installerText -match "WcpCustomSlots\.seed\.json")
Check '发布清单 SHA 可作为远端资源校验回退' ($installerText -match 'Get-ReleaseAssetSha \$remote \$seed' -and
    $installerText -match 'Get-FieldOr \$a ''sha256''')
Check '发布清单缺失字段不会中断发现' ($installerText -match 'function Get-FieldOr' -and
    $installerText -match 'Get-FieldOr \$manifest ''wordbooks''' -and
    $installerText -match 'Get-FieldOr \$release ''assets''')

# 编码守卫: 脚本含非 ASCII 时必须带 UTF-8 BOM，否则 Windows PowerShell 5.1
# 会按 ANSI 解码，静默把代码行吞进注释/字符串里（本仓库已因此吃过两次亏）。
foreach ($rel in @('..\Install-WCP-Wordbooks.ps1', '..\WordbookHub.psm1', '.\test_hub.ps1')) {
    $bytes = [IO.File]::ReadAllBytes((Join-Path $here $rel))
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $nonAscii = $false
    foreach ($byte in $bytes) { if ($byte -gt 127) { $nonAscii = $true; break } }
    Check ("$rel 编码安全(非 ASCII 必须带 BOM)") ((-not $nonAscii) -or $hasBom)
}

# 双击入口必须保持纯 ASCII: cmd.exe 按代码页读批处理，写中文就会乱码。
foreach ($rel in @('..\一键安装词书.cmd', '..\更新词书资源.cmd')) {
    $bytes = [IO.File]::ReadAllBytes((Join-Path $here $rel))
    $nonAscii = $false
    foreach ($byte in $bytes) { if ($byte -gt 127) { $nonAscii = $true; break } }
    Check ("$rel 保持 ASCII") (-not $nonAscii)
}
$installerText2 = Get-Content -LiteralPath (Join-Path $here '..\Install-WCP-Wordbooks.ps1') -Raw -Encoding UTF8
Check '交互式选择接入安装流程' ($installerText2 -match 'Resolve-InteractivePick -Rows \$rows' -and
    $installerText2 -match 'Get-HubCatalogRows -Catalog \$catalog -InstalledState \$installed')
Check '-Update 无参数时默认已安装词书' ($installerText2 -match '\$defaultIds = if \(\$Update\) \{ \$installedIds \}')
Check '安装状态使用 pack 布局版本' ($installerText -match '\$state\.layout = 2' -and
    (Get-Content -LiteralPath (Join-Path $here '..\WordbookHub.psm1') -Raw -Encoding UTF8) -match 'Layout 1')

# --- numbered rows / interactive picker -------------------------------------
# Fixture: aa installable, bb pending a release, cc installable but publishing
# no expansion size (metadata-less release).
$pickJson = @'
{
  "schema": 1,
  "wordbooks": [
    { "id": "aa", "language": "aa", "display_name": "A", "repo": "r/aa", "version": "v1",
      "word_count": 10, "es3_prefix": "aa",
      "disk": { "extract_mb": 100 },
      "assets": [ { "kind": "word_audio", "name": "aa1.zip", "size": 1048576, "sha256": "1111111111111111111111111111111111111111111111111111111111111111" } ] },
    { "id": "bb", "language": "bb", "display_name": "B", "repo": "r/bb", "version": "v1",
      "status": "pending_release", "word_count": 20, "es3_prefix": "bb",
      "disk": { "extract_mb": 200 }, "assets": [] },
    { "id": "cc", "language": "cc", "display_name": "C", "repo": "r/cc", "version": "v1",
      "word_count": 30, "es3_prefix": "cc",
      "assets": [ { "kind": "word_audio", "name": "cc1.zip", "size": 2097152, "sha256": "3333333333333333333333333333333333333333333333333333333333333333" } ] }
  ]
}
'@
$pickCat = $pickJson | ConvertFrom-Json
$pickRows = @(Get-HubCatalogRows -Catalog $pickCat -InstalledState ([pscustomobject]@{ aa = [pscustomobject]@{ version='v1'; files=[pscustomobject]@{ 'aa1.zip'=[pscustomobject]@{ sha256='1111111111111111111111111111111111111111111111111111111111111111' } } } }))
Check '编号从 1 开始且覆盖全部词书' ($pickRows.Count -eq 3 -and $pickRows[0].index -eq 1 -and $pickRows[2].index -eq 3)
Check '未发布词书标记为不可安装' ((-not $pickRows[1].installable) -and $pickRows[1].status -eq 'pending_release')
Check '已安装词书被识别' ($pickRows[0].installed -and -not $pickRows[2].installed)
Check '缺少 disk 元数据 = 解压未知' ((-not $pickRows[2].extract_known) -and $pickRows[0].extract_known)
Check '已安装词书无需下载' ($pickRows[0].download_mb -eq 0.0)

$installedIds = @(Get-InstalledBookIds -Catalog $pickCat -InstalledState ([pscustomobject]@{ aa = [pscustomobject]@{ version='v1'; files=[pscustomobject]@{} } }))
Check '已安装词书 id 列表' ($installedIds.Count -eq 1 -and $installedIds[0] -eq 'aa')

$pick = Resolve-InteractivePick -Rows $pickRows -Answer '1,3'
Check '按编号多选' ((-not $pick.cancelled) -and ($pick.ids -join ',') -eq 'aa,cc')
$pickById = Resolve-InteractivePick -Rows $pickRows -Answer 'cc'
Check '按 id 选择' (($pickById.ids -join ',') -eq 'cc')
$pickAll = Resolve-InteractivePick -Rows $pickRows -Answer 'all'
Check 'all 只取可安装的词书' (($pickAll.ids -join ',') -eq 'aa,cc')
$pickDup = Resolve-InteractivePick -Rows $pickRows -Answer '1,aa'
Check '重复选择去重' (($pickDup.ids -join ',') -eq 'aa')
$pickDefault = Resolve-InteractivePick -Rows $pickRows -Answer '' -DefaultIds @('cc')
Check '回车使用默认选择(更新已安装)' ((-not $pickDefault.cancelled) -and (($pickDefault.ids -join ',') -eq 'cc'))
$pickCancel = Resolve-InteractivePick -Rows $pickRows -Answer ''
Check '无默认时回车 = 取消' $pickCancel.cancelled
$pickQuit = Resolve-InteractivePick -Rows $pickRows -Answer 'q'
Check 'q = 取消' $pickQuit.cancelled
try { Resolve-InteractivePick -Rows $pickRows -Answer '9' | Out-Null; Check '越界编号被拒绝' $false }
catch { Check '越界编号被拒绝' ($_.Exception.Message -match '无效编号') }
try { Resolve-InteractivePick -Rows $pickRows -Answer 'zz' | Out-Null; Check '未知词书被拒绝' $false }
catch { Check '未知词书被拒绝' ($_.Exception.Message -match '未知词书') }
try { Resolve-InteractivePick -Rows $pickRows -Answer '2' | Out-Null; Check '未发布词书不能选' $false }
catch { Check '未发布词书不能选' ($_.Exception.Message -match '不可安装') }

# --- unknown expansion size must not pass silently ---------------------------
$planUnknown = New-DiskPlan -Wordbooks @($pickRows[2] | ForEach-Object { Get-WordbookById -Catalog $pickCat -Id $_.id }) -InstalledState $null
Check '缺少解压元数据时置未知标记' ($planUnknown.unknown_extract)
$compatUnknown = Test-DiskPlanCompatibility -Plan $planUnknown -FreeMb 1000
Check '未知解压空间给出提示' ($compatUnknown.extract_unknown -and $compatUnknown.message -match '未知')
$planKnown = New-DiskPlan -Wordbooks @(Get-WordbookById -Catalog $pickCat -Id 'aa') -InstalledState $null
Check '有元数据时不报未知' (-not $planKnown.unknown_extract)

Write-Host ''
Write-Host ('结果: {0} 通过, {1} 失败' -f $pass, $fail)
if ($fail -gt 0) { exit 1 } else { exit 0 }
