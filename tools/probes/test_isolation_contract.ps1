$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
$pass = 0
$fail = 0
function Check([string]$name, [bool]$condition) {
    if ($condition) { $script:pass++; Write-Host "PASS  $name" }
    else { $script:fail++; Write-Host "FAIL  $name" }
}

$sentenceSources = @{
    ja = Join-Path $root 'Japanese\mod_sentence_audio\SentenceAudioMod.cs'
    fr = Join-Path $root 'French\mod_sentence_audio_fr\SentenceAudioFrMod.cs'
    de = Join-Path $root 'German\mod_sentence_audio_de\SentenceAudioDeMod.cs'
    ru = Join-Path $root 'Russian\mod_sentence_audio_ru\SentenceAudioRuMod.cs'
    yue = Join-Path $root 'Contonese\mod_sentence_audio_yue\SentenceAudioYueMod.cs'
}
# 模板派生残留检查: 例句音频插件(除日语外)不得再携带其它语言的标识符
# (历史教训: DE/YUE 从 FR 模板批量派生, 连方法名 ManagedFrenchBookSelected
# 和日志 "(FR)" 都原样带过来了)。派生语言用语言无关命名 ManagedBookSelected。
foreach ($language in $sentenceSources.Keys) {
    $text = Get-Content -LiteralPath $sentenceSources[$language] -Raw -Encoding UTF8
    if ($language -eq 'ja') {
        Check 'ja sentence_dir_pack_only' (
            $text.Contains('PackLangCode = "ja"') -and
            $text.Contains('audio", "sentence"') -and
            -not $text.Contains('ja_sentence_audio'))
    } else {
        # 2026-09-16 B 类改造后，非日语例句插件同样只读 pack（legacy 目录
        # <lang>_sentence_audio 回退已移除），与日语同一条判据。
        Check "$language sentence_dir_pack_only" (
            $text.Contains('PackLangCode = "' + $language + '"') -and
            $text.Contains('audio", "sentence"') -and
            -not ($text -match ($language + '_sentence_audio')))
        Check "$language sentence_mod_language_clean" (
            -not ($text -match 'FrenchBookSelected') -and
            -not ($text -match 'OnButton1Click \(FR\)'))
    }
}

$wordSources = @(
    (Join-Path $root 'Japanese\mod_jp_wordlist\JpWordListMod.cs'),
    (Join-Path $root 'French\mod_fr_wordlist\FrWordListMod.cs'),
    (Join-Path $root 'German\mod_de_wordlist\DeWordListMod.cs'),
    (Join-Path $root 'Russian\mod_ru_wordlist\RuWordListMod.cs'),
    (Join-Path $root 'Contonese\mod_yue_wordlist\YueWordListMod.cs')
)
foreach ($path in $wordSources) {
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    Check "$(Split-Path $path -Leaf) shared_db_write_gate" (
        $text -match 'AllowSharedDatabaseWrites' -and
        $text -match 'Config\.Bind\("Legacy", "AllowSharedDatabaseWrites", false')
}

$ru = [IO.File]::ReadAllText((Join-Path $root 'Russian\mod_ru_wordlist\RuWordListMod.cs'))
Check 'ru_word_audio_no_shared_fallback' ($ru -notmatch 'Path\.Combine\(Application\.persistentDataPath,\s*"vocabulary"')

$ruGeneratorText = [IO.File]::ReadAllText((Join-Path $root 'Russian\tools\gen_sentence_audio_ru.py'))
$jaBuilderText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\wcp_wordbooks\tools\build_installer_payload.py'))
$jaInstallerText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\wcp_wordbooks\installer\Install-WCP-Japanese.ps1'))
$jaWordGeneratorText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\wcp_wordbooks\tools\gen_audio.py'))
$jaSentenceGeneratorText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\wcp_wordbooks\tools\gen_sentence_audio.py'))
$hostManifestText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_host\Core\Manifest.cs'))
$hostStrategyText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_host\Core\GenericLanguageStrategy.cs'))
$slotModelText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_custom_slots\CustomSlotModel.cs'))
$slotUiText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_custom_slots\CustomSlotsMod.cs'))

Check 'ru_sentence_generator_private' ([bool]($ruGeneratorText -match 'ru_sentence_audio'))
Check 'ja_installer ships_host_and_slots' ([bool](
    ($jaBuilderText -match "'WcpHost\.dll'") -and
    ($jaBuilderText -match "'CustomSlotsMod\.dll'") -and
    ($jaInstallerText -match '\$pluginNames')
))
Check 'ja_installer_writes_pack_audio' ([bool](
    ($jaInstallerText -match '\$packsRoot') -and
    ($jaInstallerText -match '\$jaWordAudio') -and
    ($jaInstallerText -match '\$jaSentenceAudio')
))
Check 'ja_generators_are_pack_scoped' ([bool](
    ($jaWordGeneratorText -match 'packs.*ja.*audio.*word') -and
    ($jaSentenceGeneratorText -match 'packs.*ja.*audio.*sentence')
))
Check 'host_allows_host_strategy' ([bool]($hostManifestText -match '\$host'))
Check 'generic_strategy_bound_resources' ([bool](($hostStrategyText -match 'BindPack') -and ($hostStrategyText -match 'MeaningDbPath')))
Check 'custom_slots_max_20' ([bool]($slotModelText -match 'MaxSlots = 20'))
Check 'custom_slots_scroll_page' ([bool](($slotUiText -match 'ScrollRect') -and ($slotUiText -match 'RebuildRows')))

# -- 2026-09-15 cross-language leak root-cause fixes --
# Battle pools must be rebuilt from the selected book; the global learned-word
# dictionary may only influence ordering, never the candidate set.  A second
# rule: only one plugin may own the runtime patches, so legacy language
# plugins yield once the host reports the language as managed.
$hostRuntimeText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_host\HostRuntime.cs'))
$hostPatchesText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_host\HostPatches.cs'))
$hostMainText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_host\Host.cs'))
$bookPoolText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_host\Core\BookPool.cs'))
$gameStatsText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_host\Core\GameLearnedStats.cs'))
$takeoverText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_host\TakeoverScope.cs'))
$hubInstallerText = [IO.File]::ReadAllText((Join-Path $root 'hub\Install-WCP-Wordbooks.ps1'))
$registrySourceText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\mod_book_name\BookProfiles.cs'))
$profileGeneratorText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\tools\gen_bookprofiles.py'))
$legacyPlugins = @(
    'Japanese\mod_jp_wordlist\JpWordListMod.cs',
    'French\mod_fr_wordlist\FrWordListMod.cs',
    'German\mod_de_wordlist\DeWordListMod.cs',
    'Russian\mod_ru_wordlist\RuWordListMod.cs',
    'Contonese\mod_yue_wordlist\YueWordListMod.cs'
)

Check 'pool_rebuilt_from_current_book' ([bool](
    ($bookPoolText -match 'Rebuild\(') -and
    ($bookPoolText -match 'FilterOnly') -and
    ($bookPoolText -match 'ILearnedStats')
))
Check 'pool_has_no_placeholder_padding' ([bool](-not ($bookPoolText -match '"one"|"five"')))
Check 'pool_reads_global_stats_as_view_only' ([bool](
    ($gameStatsText -match 'HaveLearnedDictionary') -and
    -not ($gameStatsText -match 'S7TestWordList_Para|S9CurrentArray_Para')
))
Check 'host_owns_fight_topup_prefix' ([bool](
    ($hostPatchesText -match 'PoolPrefix') -and
    ($hostRuntimeText -match 'PrefixPool') -and
    ($takeoverText -match 'RebuildPool') -and
    ($takeoverText -match 'StatsProvider')
))
Check 'host_marks_managed_languages' ([bool](
    ($hostMainText -match 'WcpHost\.managed\.txt') -and
    ($hostMainText -match 'ResourcesReady') -and
    ($hostManifestText -match 'internal bool ResourcesReady')
))
Check 'slot_collision_keeps_language_pack' ([bool](
    ($hostManifestText -match 'old\.ObservedSlot == m\.Profile\.ObservedSlot') -and
    ($hostManifestText -match '_warnings\.Add\("observed_slot')
))
Check 'installers_register_managed_languages' ([bool](
    ($jaInstallerText -match 'WcpHost\.managed\.txt') -and
    ($hubInstallerText -match 'WcpHost\.managed\.txt')
))
Check 'registry_covers_pack_in_language_project' ([bool](
    ($registrySourceText -match 'catbar-cantonese-complete') -and
    ($profileGeneratorText -match 'def pack_roots')
))

$legacyYieldOk = $true
foreach ($legacyPath in $legacyPlugins) {
    $text = [IO.File]::ReadAllText((Join-Path $root $legacyPath))
    if (-not ($text -match 'YieldToHost' -and $text -match 'HostTakesOver' -and
              $text -match 'WcpHost\.managed\.txt')) { $legacyYieldOk = $false }
}
Check 'legacy_plugins_yield_to_host' $legacyYieldOk

$templateClean = $true
$templateTargets = [ordered]@{
    'Japanese\mod_jp_wordlist\JpWordListMod.cs' = @('DEWordList:', 'WCP DE Word List')
    'French\mod_fr_wordlist\FrWordListMod.cs' = @('FrenchBookSelected', 'FrenchProbeOk', 'frOkFull', 'frOkOnly', 'PlayFrenchWord', 'DEWordList:')
    'German\mod_de_wordlist\DeWordListMod.cs' = @('FrenchBookSelected', 'FrenchProbeOk', 'frOkFull', 'frOkOnly', 'PlayFrenchWord', 'WCP FR Word List', 'catbar-french-cefr-complete')
    'Russian\mod_ru_wordlist\RuWordListMod.cs' = @('FrenchBookSelected', 'FrenchProbeOk', 'frOkFull', 'frOkOnly', 'PlayFrenchWord', 'catbar-french-cefr-complete')
    'Contonese\mod_yue_wordlist\YueWordListMod.cs' = @('FrenchBookSelected', 'FrenchProbeOk', 'frOkFull', 'frOkOnly', 'PlayFrenchWord', 'DEWordList:', 'WCP DE Word List', 'catbar-french-cefr-complete')
}
foreach ($legacyPath in $templateTargets.Keys) {
    $text = [IO.File]::ReadAllText((Join-Path $root $legacyPath))
    foreach ($token in $templateTargets[$legacyPath]) {
        if ($text -match [regex]::Escape($token)) { $templateClean = $false }
    }
}
Check 'legacy_plugins_are_language_clean' $templateClean

# -- 2026-09-15 资源化扩展点: 加一种语言 = 加一个 pack.build.json + 资源 ----
# 项目**自动发现**: 根目录下任何带 packs\ 子目录的都是语言工程; 集成仓库/
# hub 这类"带顶层 Install-WCP-Wordbooks.ps1 的分发仓库"被排除 —— 它们的
# packs\ 只是清单载体, 不承担物化职责。追加语言时不需要改这个文件。
$projectNames = @()
foreach ($candidate in @(Get-ChildItem -LiteralPath $root -Directory)) {
    if (Test-Path -LiteralPath (Join-Path $candidate.FullName 'packs') -PathType Container) {
        if (-not (Test-Path -LiteralPath (Join-Path $candidate.FullName 'Install-WCP-Wordbooks.ps1'))) {
            $projectNames += $candidate.Name
        }
    }
}
$packDirs = New-Object System.Collections.Generic.List[object]
foreach ($project in $projectNames) {
    $packsRootForProject = Join-Path (Join-Path $root $project) 'packs'
    foreach ($packDir in @(Get-ChildItem -LiteralPath $packsRootForProject -Directory)) {
        $packDirs.Add($packDir)
    }
}
Check 'pack_dirs_discovered' ($packDirs.Count -ge 4)

$specMissing = @()
$incomplete = @()
$nonResourceStrategy = @()
foreach ($packDir in $packDirs) {
    $language = $packDir.Name
    $manifestPath = Join-Path $packDir.FullName 'manifest.json'
    $specPath = Join-Path $packDir.FullName 'pack.build.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) { continue }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    # 分类: 资源包(strategy.assembly='$host')必须有 pack.build.json(数据来源配方);
    # 策略包自带行为程序集(如 ja/yue), 数据由策略工程自己构建, 不需要 spec。
    $isStrategyPack = ($manifest.strategy -and
                       [string]$manifest.strategy.assembly -ne '$host')
    if (-not $isStrategyPack -and -not (Test-Path -LiteralPath $specPath)) {
        $specMissing += $language; continue
    }
    foreach ($rel in @($manifest.resources.meaning_db, $manifest.resources.sentence_table,
                       $manifest.resources.repair) + @($manifest.resources.books)) {
        if (-not $rel) { continue }
        if (-not (Test-Path -LiteralPath (Join-Path $packDir.FullName $rel))) {
            $incomplete += "$language/$rel"
        }
    }
    # 分类: 策略包自带行为程序集(ja/yue), 资源包走宿主通用策略($host)。
    # 除已知策略语言外, 任何语言都不允许携带私有策略 DLL —— 这是"只提供
    # 资源"的硬约束; 新策略语言必须在下一行登记。
    $strategyLanguages = @('ja', 'yue')
    if ($isStrategyPack -and ($strategyLanguages -notcontains $language)) {
        $nonResourceStrategy += "$language=unexpected-strategy-pack"
    }
    if (-not $isStrategyPack -and ($strategyLanguages -contains $language)) {
        $nonResourceStrategy += "$language=missing-strategy-assembly"
    }
}
Check 'pack_specs_present' ($specMissing.Count -eq 0)
Check 'pack_resources_complete' ($incomplete.Count -eq 0)
Check 'pack_strategy_resource_only' ($nonResourceStrategy.Count -eq 0)

# catalog 身份字段必须与 pack manifest 一致。2026-09-15 实测: es/pt 的 catalog 里
# 存的是 verify_all_es/pt.py 的**旧指纹算法**（'\n'.join 无尾换行），与宿主
# 逐词 + '\n' 的实现不同 —— 装好词书后身份门永远不命中。任何一处漂移都要报 FAIL。
$catalogPath = Join-Path $root 'MultiLanguage\catalog.json'
if (Test-Path -LiteralPath $catalogPath) {
    $catalog = Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $identityDrift = @()
    foreach ($wb in @($catalog.wordbooks)) {
        $manifestPath = Join-Path (Join-Path $root "MultiLanguage\packs") (Join-Path ([string]$wb.id) 'manifest.json')
        if (-not (Test-Path -LiteralPath $manifestPath)) { continue }
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([int]$wb.word_count -ne [int]$manifest.word_count) {
            $identityDrift += ("$($wb.id):word_count $($wb.word_count)!=$($manifest.word_count)")
        }
        if ([string]$wb.fingerprint_sha256 -ne [string]$manifest.fingerprint_sha256) {
            $identityDrift += ("$($wb.id):fingerprint")
        }
        if ([string]$wb.es3_prefix -ne [string]$manifest.es3_prefix) {
            $identityDrift += ("$($wb.id):es3_prefix")
        }
    }
    Check 'catalog_identity_matches_pack' ($identityDrift.Count -eq 0)
    if ($identityDrift.Count -gt 0) {
        Write-Host ("      漂移: " + ($identityDrift -join ', '))
    }
}

$packBuilderText = [IO.File]::ReadAllText((Join-Path $root 'Japanese\tools\build_pack.py'))
# 语言数据只能来自 spec: 载荷目录 / 文件名 / 词书清单都不能写死在构建器里。
$specDriven = $true
foreach ($token in @('spec["payload_dir"]', 'spec["pron"]', 'spec["sentences"]',
                     'spec["books"]', 'spec["strategy"]')) {
    if (-not $packBuilderText.Contains($token)) { $specDriven = $false }
}
Check 'pack_builder_is_spec_driven' $specDriven

$builderCheck = $null
$previousPythonUtf8 = $env:PYTHONUTF8
$env:PYTHONUTF8 = '1'
# 依赖前置: 构建器读词书需要 openpyxl。缺依赖是环境问题不是数据问题,
# 必须显式 SKIP 而不是把"没装包"当成"包数据漂移"报 FAIL。
# 本脚本开头是 $ErrorActionPreference='Stop': Windows PowerShell 5.1 会把
# 原生命令的 stderr(即使 2>$null)包装成终止错误, 因此这段必须临时降到
# Continue, 否则探测 openpyxl 本身就会把整个脚本打死。
$previousEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$hasOpenpyxl = $true
& python -c "import openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) {
    $hasOpenpyxl = $false
    Write-Host "SKIP  pack_data_matches_specs (PATH 上的 python 缺 openpyxl; 用系统 Python 或 pip install openpyxl 后重跑)"
}
if ($hasOpenpyxl) {
    $builderCheck = & python (Join-Path $root 'Japanese\tools\build_pack.py') --check-all $root 2>&1
    $builderExit = $LASTEXITCODE
    Check 'pack_data_matches_specs' ($builderExit -eq 0)
}
$ErrorActionPreference = $previousEap
if ($null -eq $previousPythonUtf8) { Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue }
else { $env:PYTHONUTF8 = $previousPythonUtf8 }

$payloadDir = @(Get-ChildItem -LiteralPath (Join-Path $root 'Japanese\wcp_wordbooks\output\installer_pkg') -Directory -Filter 'WCP*' -ErrorAction SilentlyContinue)
if ($payloadDir.Count -gt 0) {
    $payloadHost = Join-Path $payloadDir[0].FullName 'support\payload\plugins\WcpHost.dll'
    if (Test-Path -LiteralPath $payloadHost) {
        Check 'payload_host_matches_repo_build' ([bool](
            (Get-FileHash -LiteralPath $payloadHost -Algorithm SHA256).Hash -eq
            (Get-FileHash -LiteralPath (Join-Path $root 'Japanese\mod_host\WcpHost.dll') -Algorithm SHA256).Hash
        ))
    }
}
Write-Host ""
Write-Host "Result: $pass passed, $fail failed"
if ($fail -gt 0) { exit 1 }
