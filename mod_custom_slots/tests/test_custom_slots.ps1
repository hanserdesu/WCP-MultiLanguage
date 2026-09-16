$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
# 源文件是无 BOM UTF-8，PS 5.1 默认按 ANSI 解码会毁掉中文断言，必须显式 -Encoding UTF8
$model = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'CustomSlotModel.cs')
$plugin = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'CustomSlotsMod.cs')
$compat = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'GameCompat.cs')
$pass = 0
$fail = 0
function Check([bool]$ok, [string]$name) {
    if ($ok) { Write-Host "  PASS  $name"; $script:pass++ }
    else { Write-Host "  FAIL  $name"; $script:fail++ }
}
Check ($model -match 'MaxSlots = 20') 'logical slot limit is 20'
Check ($model -match 'NativeSlots = 4') 'native slot boundary remains 4'
Check ($plugin -match 'ScrollRect') 'single scrollable page'
Check ($plugin -match 'WcpCustomSlots\.seed\.json') 'installer seed interface'
Check ($plugin -match 'NativeSlotOwnedByManaged') 'external book overwrite boundary'
Check ($plugin -match 'NativeSlotOwnedByManaged') 'only reuse mod-owned native slot'
Check ($plugin -notmatch 'SelfBookList5') 'no fake fifth native slot'
# 2026-09-16 实机修复：BookNameMod 把书名行改写成「…(猫条版)」后页面判据失效，
# 面板建好 0.25s 内被轮询藏掉。判据必须认美化形态 + 有页签点击兜底 + 多实例感知。
Check ($plugin -match 'CalledFromUserClick') 'user click recorded via UGUI stack frames'
Check ($plugin -match 'FindVisibleChooserInstance') 'poll uses the visible chooser instance'
Check ($compat -match '猫条版') 'page predicate accepts cosmetic book names (BookNameMod)'

# 静态契约之外，再拿真实模型跑一遍 20 条逻辑槽与原生槽边界的行为测试。
# 子进程必须真的跑起来：拿不到 `Failures: 0` 就算失败，避免“没启动”被当成通过。
$childScript = Join-Path $PSScriptRoot 'run_slot_rules_test.ps1'
$childLines = @(& powershell -NoProfile -ExecutionPolicy Bypass -File $childScript 6>&1)
$childCode = $LASTEXITCODE
$childText = ($childLines | ForEach-Object { [string]$_ }) -join "`n"
$childLines | ForEach-Object { Write-Host $_ }
Check (($childCode -eq 0) -and ($childText -match 'Failures: 0')) 'slot rules behavioural harness'

Write-Host "`nResult: $pass passed, $fail failed"
if ($fail -gt 0) { exit 1 }
