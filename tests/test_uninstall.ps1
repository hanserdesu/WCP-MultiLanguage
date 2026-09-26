$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$scratch = [IO.Path]::GetFullPath((Join-Path $repo ('_local\test-uninstall-' + [guid]::NewGuid().ToString('N'))))
$allowed = [IO.Path]::GetFullPath((Join-Path $repo '_local')) + [IO.Path]::DirectorySeparatorChar
if (-not $scratch.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw '测试路径越界' }
$pass = 0
function Check([string]$name, $ok) {
    if ($ok -isnot [bool]) { throw ('Bad assertion value for ' + $name + ': ' + $ok.GetType().FullName) }
    if (-not $ok) { throw ('FAIL ' + $name) }
    $script:pass++
    Write-Host ('PASS ' + $name)
}
try {
    $dataRoot = Join-Path $scratch 'data'
    $game = Join-Path $scratch 'game'
    $wcp = Join-Path $dataRoot 'wcp'
    $fr = Join-Path $dataRoot 'packs\fr'
    $de = Join-Path $dataRoot 'packs\de'
    foreach ($dir in @($wcp, $fr, $de, $game)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $catalog = Get-Content -LiteralPath (Join-Path $repo 'catalog.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $frBook = @($catalog.wordbooks | Where-Object { $_.id -eq 'fr' })[0]
    $deBook = @($catalog.wordbooks | Where-Object { $_.id -eq 'de' })[0]
    $statePath = Join-Path $wcp 'hub-state.json'
    $state = [pscustomobject]@{ schema=2; layout=2; game=$game; wordbooks=[pscustomobject]@{
        fr=[pscustomobject]@{ version=$frBook.version; files=[pscustomobject]@{} }
        de=[pscustomobject]@{ version=$deBook.version; files=[pscustomobject]@{} }
    } }
    $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statePath -Encoding UTF8
    $emptyResources = [pscustomobject]@{ books=@(); meaning_db=''; sentence_table=''; repair='' }
    $frManifest = [pscustomobject]@{ language='fr'; profile_id='wrong'; resources=$emptyResources }
    $deManifest = [pscustomobject]@{ language='de'; profile_id=$deBook.profile_id; resources=$emptyResources }
    $frManifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $fr 'manifest.json') -Encoding UTF8
    $deManifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $de 'manifest.json') -Encoding UTF8
    [IO.File]::WriteAllText((Join-Path $fr 'word.mp3'), 'fixture')
    [IO.File]::WriteAllText((Join-Path $de 'word.mp3'), 'other')
    $slots = [pscustomobject]@{ schema=1; selected=1; slots=@(
        [pscustomobject]@{ number=1; id=$frBook.profile_id; name='French'; language='fr'; owner='mod'; managed=$true; nativeSlot=1; words=@('bonjour') },
        [pscustomobject]@{ number=2; id='native-2'; name='Other'; language=''; owner='external'; managed=$false; nativeSlot=2; words=@('third-party') }
    ) }
    foreach ($name in @('WcpCustomSlots.json', 'WcpCustomSlots.seed.json')) {
        $slots | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $wcp $name) -Encoding UTF8
    }
    $installer = Join-Path $repo 'Install-WCP-Wordbooks.ps1'
    $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$installer,'-Uninstall','-Offline',
              '-CatalogPath',(Join-Path $repo 'catalog.json'),'-GameDir',$game,
              '-DataRoot',$dataRoot,'-StatePath',$statePath,'-Books','fr','-Yes')
    try { & powershell.exe @args 2>&1 | Out-Null } catch { }
    $rejected = ($LASTEXITCODE -ne 0) -and (Test-Path -LiteralPath $fr)
    Check '清单身份错误时拒绝删除' $rejected
    $frManifest.profile_id = $frBook.profile_id
    $frManifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $fr 'manifest.json') -Encoding UTF8
    & powershell.exe @args 2>&1 | Out-Null
    Check '仅删除选中的语言包' ($LASTEXITCODE -eq 0 -and -not (Test-Path -LiteralPath $fr) -and
        (Test-Path -LiteralPath (Join-Path $de 'word.mp3')))
    $newState = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    Check '状态只摘除目标词书' (-not $newState.wordbooks.PSObject.Properties['fr'] -and
        $null -ne $newState.wordbooks.PSObject.Properties['de'])
    foreach ($name in @('WcpCustomSlots.json', 'WcpCustomSlots.seed.json')) {
        $newSlots = Get-Content -LiteralPath (Join-Path $wcp $name) -Raw -Encoding UTF8 | ConvertFrom-Json
        Check ($name + ' 只清理受管行') ($newSlots.slots[0].id -eq '' -and
            $newSlots.slots[1].id -eq 'native-2' -and $newSlots.slots[1].words[0] -eq 'third-party' -and
            $newSlots.selected -eq 0)
    }
    $marker = Join-Path $game 'BepInEx\config\WcpHost.managed.txt'
    Check '受管语言登记保留其他语言' ((Get-Content -LiteralPath $marker -Raw) -match 'de' -and
        (Get-Content -LiteralPath $marker -Raw) -notmatch 'fr')

    $runnerDir = Join-Path $scratch 'runner'
    New-Item -ItemType Directory -Path $runnerDir | Out-Null
    Copy-Item -LiteralPath (Join-Path $repo 'run-installer.ps1') -Destination $runnerDir
    @'
param([switch]$Update,[switch]$Uninstall,[string[]]$Books)
([pscustomobject]@{ update=[bool]$Update; uninstall=[bool]$Uninstall; books=@($Books) }) |
    ConvertTo-Json -Compress | Set-Content -LiteralPath $env:WCP_TEST_ARGS_OUT
'@ | Set-Content -LiteralPath (Join-Path $runnerDir 'Install-WCP-Wordbooks.ps1') -Encoding UTF8
    $env:WCP_TEST_ARGS_OUT = Join-Path $runnerDir 'args.json'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $runnerDir 'run-installer.ps1') -Update | Out-Null
    $bound = Get-Content -LiteralPath $env:WCP_TEST_ARGS_OUT -Raw | ConvertFrom-Json
    Check '更新开关不会被绑定成词书名' ($LASTEXITCODE -eq 0 -and $bound.update -and
        $null -eq $bound.books)
} finally {
    Remove-Item Env:WCP_TEST_ARGS_OUT -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $scratch) { Remove-Item -LiteralPath $scratch -Recurse -Force }
}
Write-Host ("结果: $pass 通过")
