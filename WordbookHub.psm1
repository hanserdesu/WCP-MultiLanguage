# WordbookHub.psm1 — catalog, selection, disk-plan and diff logic for the
# unified WCP multi-language wordbook installer.
#
# This module is deliberately free of network and filesystem writes: it only
# reads a catalog JSON and computes decisions, so it can be unit-tested offline
# (see tests/test_hub.ps1). The CLI entry point (Install-WCP-Wordbooks.ps1)
# supplies all I/O.
#
# Catalog contract (hub/catalog.json):
#   { schema, updated, wordbooks: [
#       { id, language, display_name, repo, release_tag, version,
#         status, word_count, fingerprint_sha256, es3_prefix,
#         disk: { extract_mb, game_mb },
#         assets: [ { kind, name, size, sha256, url } ] } ] }

Set-StrictMode -Version Latest

$script:BytesPerMb = 1048576

function Get-PropertyNames($Object) {
    if ($null -eq $Object) { return @() }
    return @($Object.PSObject.Properties | ForEach-Object { $_.Name })
}

function Import-WordbookCatalog {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { throw "catalog 不存在: $Path" }
    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $cat = $null
    try { $cat = $raw | ConvertFrom-Json } catch { throw "catalog JSON 解析失败: $($_.Exception.Message)" }
    Assert-WordbookCatalog -Catalog $cat
    return $cat
}

function Assert-WordbookCatalog {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Catalog)

    $names = Get-PropertyNames $Catalog
    foreach ($f in @('schema', 'wordbooks')) {
        if ($names -notcontains $f) { throw "catalog 缺少字段: $f" }
    }
    $wbs = @($Catalog.wordbooks)
    if ($wbs.Count -eq 0) { throw "catalog 未包含任何词书" }

    $seen = @{}
    foreach ($wb in $wbs) {
        $wn = Get-PropertyNames $wb
        foreach ($f in @('id', 'language', 'display_name', 'repo', 'version', 'assets')) {
            if ($wn -notcontains $f) { throw "词书缺少字段 '$f' (id=$($wb.id))" }
        }
        if ([string]::IsNullOrWhiteSpace($wb.id)) { throw "词书 id 不能为空" }
        if ($seen.ContainsKey($wb.id)) { throw "词书 id 重复: $($wb.id)" }
        $seen[$wb.id] = $true

        $status = if ($wn -contains 'status' -and $wb.status) { ([string]$wb.status).ToLowerInvariant() } else { 'available' }
        if ($status -notin @('available', 'pending_release', 'unavailable')) {
            throw "词书 '$($wb.id)' 的 status 无效: $status"
        }
        $assets = @($wb.assets)
        if ($status -eq 'available' -and $assets.Count -eq 0) {
            throw "词书 '$($wb.id)' 标记为 available 但没有任何资源"
        }
        foreach ($a in $assets) {
            $an = Get-PropertyNames $a
            foreach ($f in @('kind', 'name', 'size', 'sha256')) {
                if ($an -notcontains $f) { throw "词书 '$($wb.id)' 的资源缺少字段 '$f'" }
            }
            if ([int64]$a.size -le 0) { throw "资源 '$($a.name)' 的 size 必须为正数" }
            if (([string]$a.sha256) -notmatch '^[0-9a-fA-F]{64}$') { throw "资源 '$($a.name)' 的 sha256 必须是 64 位十六进制" }
        }
    }
}

function Get-WordbookById {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Catalog, [Parameter(Mandatory = $true)][string]$Id)

    foreach ($wb in @($Catalog.wordbooks)) {
        if ($wb.id -ieq $Id) { return $wb }
    }
    throw "catalog 中没有词书: $Id"
}

# Turns a user selection into concrete wordbook objects. Unknown ids are a hard
# error so a typo never silently installs nothing.
function Resolve-WordbookSelection {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$Catalog,
        [string[]]$Ids,
        [switch]$All
    )

    if ($All) {
        $available = @($Catalog.wordbooks | Where-Object {
            $s = if ((Get-PropertyNames $_) -contains 'status' -and $_.status) { [string]$_.status } else { 'available' }
            $s -ieq 'available'
        })
        if ($available.Count -eq 0) { throw 'catalog 中没有可安装词书' }
        return $available
    }
    if (-not $Ids -or @($Ids).Count -eq 0) { throw "未选择任何词书 (使用 -Books 或 -All)" }

    $picked = New-Object System.Collections.Generic.List[object]
    $used = @{}
    foreach ($raw in @($Ids)) {
        foreach ($piece in ([string]$raw).Split(',')) {
            $id = $piece.Trim()
            if ($id -eq '') { continue }
            $wb = Get-WordbookById -Catalog $Catalog -Id $id
            $status = if ((Get-PropertyNames $wb) -contains 'status' -and $wb.status) { [string]$wb.status } else { 'available' }
            if ($status -ine 'available') {
                throw "词书 '$id' 当前不可安装 (status=$status；资源发布后再试)"
            }
            if (-not $used.ContainsKey($wb.id)) { $used[$wb.id] = $true; $picked.Add($wb) }
        }
    }
    if ($picked.Count -eq 0) { throw "未选择任何词书" }
    return $picked.ToArray()
}

function Get-HubFileRecord {
    param($InstalledState, [string]$BookId, [string]$AssetName)
    if (-not $InstalledState) { return $null }
    $names = Get-PropertyNames $InstalledState
    if ($names -notcontains $BookId) { return $null }
    $book = $InstalledState.$BookId
    if (-not $book.files) { return $null }
    $fnames = Get-PropertyNames $book.files
    if ($fnames -notcontains $AssetName) { return $null }
    return $book.files.$AssetName
}

# Assets that are new or whose recorded sha256 differs from what is installed.
function Get-WordbookAssetDiff {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Wordbook, $InstalledState)

    $need = New-Object System.Collections.Generic.List[object]
    foreach ($a in @($Wordbook.assets)) {
        $have = Get-HubFileRecord -InstalledState $InstalledState -BookId $Wordbook.id -AssetName $a.name
        if (-not $have -or ([string]$have.sha256) -ne ([string]$a.sha256)) { $need.Add($a) }
    }
    return $need.ToArray()
}

function Test-WordbookInstalledFully {
    param($Wordbook, $InstalledState)
    $status = if ((Get-PropertyNames $Wordbook) -contains 'status' -and $Wordbook.status) { [string]$Wordbook.status } else { 'available' }
    if ($status -ine 'available') { return $false }
    if (-not $InstalledState) { return $false }
    $names = Get-PropertyNames $InstalledState
    if ($names -notcontains $Wordbook.id) { return $false }
    $book = $InstalledState.($Wordbook.id)
    if ([string]$book.version -ne [string]$Wordbook.version) { return $false }
    return (@(Get-WordbookAssetDiff -Wordbook $Wordbook -InstalledState $InstalledState).Count -eq 0)
}

function Get-ExtractMb {
    param($Wordbook)
    if ((Get-PropertyNames $Wordbook) -notcontains 'disk') { return 0.0 }
    $disk = $Wordbook.disk
    if (-not $disk) { return 0.0 }
    if ((Get-PropertyNames $disk) -notcontains 'extract_mb') { return 0.0 }
    return [double]$disk.extract_mb
}

# A book whose metadata declares no expansion size cannot be preflighted
# truthfully.  Report it instead of pretending the 0 MB default is a measurement,
# so the installer warns the user rather than silently passing the disk gate.
function Test-ExtractKnown {
    param($Wordbook)
    if ((Get-PropertyNames $Wordbook) -notcontains 'disk') { return $false }
    $disk = $Wordbook.disk
    if (-not $disk) { return $false }
    if ((Get-PropertyNames $disk) -notcontains 'extract_mb') { return $false }
    return ([double]$disk.extract_mb -gt 0)
}

# Numbered catalog view shared by -List and the interactive picker.  Index is
# 1-based so it can be typed directly at the prompt.
function Get-HubCatalogRows {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Catalog, $InstalledState)

    $rows = New-Object System.Collections.Generic.List[object]
    $index = 0
    foreach ($wb in @($Catalog.wordbooks)) {
        $index++
        $names = Get-PropertyNames $wb
        $status = if (($names -contains 'status') -and $wb.status) { [string]$wb.status } else { 'available' }
        $needBytes = [int64]0
        foreach ($a in (Get-WordbookAssetDiff -Wordbook $wb -InstalledState $InstalledState)) { $needBytes += [int64]$a.size }
        $rows.Add([pscustomobject]@{
            index        = $index
            id           = [string]$wb.id
            display_name = [string]$wb.display_name
            version      = [string]$wb.version
            word_count   = if ($names -contains 'word_count') { [int]$wb.word_count } else { 0 }
            status       = $status
            installable  = ($status -ieq 'available')
            installed    = (Test-WordbookInstalledFully -Wordbook $wb -InstalledState $InstalledState)
            download_mb  = [math]::Round($needBytes / $script:BytesPerMb, 1)
            extract_mb   = [math]::Round((Get-ExtractMb $wb), 1)
            extract_known = (Test-ExtractKnown $wb)
        })
    }
    return $rows.ToArray()
}

function Get-InstalledBookIds {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Catalog, $InstalledState)

    $ids = New-Object System.Collections.Generic.List[string]
    if (-not $InstalledState) { return $ids.ToArray() }
    $have = Get-PropertyNames $InstalledState
    foreach ($wb in @($Catalog.wordbooks)) {
        if ($have -contains $wb.id) { $ids.Add([string]$wb.id) }
    }
    return $ids.ToArray()
}

# Parses one line of user input against the numbered rows.  Accepts numbers,
# ids, "all", or an empty answer (which takes DefaultIds).  Kept pure so the
# prompt logic is covered by the offline unit tests instead of a live console.
function Resolve-InteractivePick {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$Rows,
        [string]$Answer,
        [string[]]$DefaultIds = @()
    )

    $rows = @($Rows)
    $text = if ($null -eq $Answer) { '' } else { ([string]$Answer).Trim() }

    if ($text -eq '') {
        $defaults = New-Object System.Collections.Generic.List[string]
        foreach ($id in @($DefaultIds)) {
            if ([string]::IsNullOrWhiteSpace([string]$id)) { continue }
            $defaults.Add([string]$id)
        }
        if ($defaults.Count -eq 0) { return [pscustomobject]@{ cancelled = $true; ids = @() } }
        return [pscustomobject]@{ cancelled = $false; ids = $defaults.ToArray() }
    }

    if ($text -match '^(q|quit|cancel|取消)$') { return [pscustomobject]@{ cancelled = $true; ids = @() } }

    if ($text -match '^(all|a|\*|全部)$') {
        $all = New-Object System.Collections.Generic.List[string]
        foreach ($row in $rows) { if ($row.installable) { $all.Add([string]$row.id) } }
        if ($all.Count -eq 0) { throw '没有可安装的词书' }
        return [pscustomobject]@{ cancelled = $false; ids = $all.ToArray() }
    }

    $picked = New-Object System.Collections.Generic.List[string]
    foreach ($piece in ($text -split '[,、;\s]+')) {
        $token = $piece.Trim()
        if ($token -eq '') { continue }
        $row = $null
        if ($token -match '^[0-9]+$') {
            $wanted = [int]$token
            foreach ($candidate in $rows) { if ($candidate.index -eq $wanted) { $row = $candidate; break } }
            if (-not $row) { throw "无效编号: $token (可选 1-$($rows.Count))" }
        } else {
            foreach ($candidate in $rows) { if ([string]$candidate.id -ieq $token) { $row = $candidate; break } }
            if (-not $row) { throw "未知词书: $token" }
        }
        if (-not $row.installable) { throw "词书 '$($row.id)' 当前不可安装 (status=$($row.status)；资源发布后再试)" }
        if (-not $picked.Contains([string]$row.id)) { $picked.Add([string]$row.id) }
    }
    if ($picked.Count -eq 0) { throw '没有选定任何词书' }
    return [pscustomobject]@{ cancelled = $false; ids = $picked.ToArray() }
}

# Peak-disk plan: during an install the downloaded archives and their extracted
# contents coexist, so peak = download + extract. final = extract (archives are
# deleted afterwards). Already-fully-installed books contribute download only
# for changed assets and no new extract footprint.
function New-DiskPlan {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Wordbooks, $InstalledState)

    $downloadBytes = [int64]0
    $extractBytes = [int64]0
    $unknownExtract = $false
    $rows = New-Object System.Collections.Generic.List[object]

    foreach ($wb in @($Wordbooks)) {
        $needBytes = [int64]0
        $needNames = New-Object System.Collections.Generic.List[string]
        foreach ($a in (Get-WordbookAssetDiff -Wordbook $wb -InstalledState $InstalledState)) {
            $needBytes += [int64]$a.size
            $needNames.Add($a.name)
        }
        $full = Test-WordbookInstalledFully -Wordbook $wb -InstalledState $InstalledState
        $extractThis = if ($full) { [int64]0 } else { [int64][math]::Round((Get-ExtractMb $wb) * $script:BytesPerMb) }
        $extractKnown = Test-ExtractKnown $wb
        if (-not $full -and -not $extractKnown) { $unknownExtract = $true }

        $downloadBytes += $needBytes
        $extractBytes += $extractThis
        $rows.Add([pscustomobject]@{
            id         = $wb.id
            version    = $wb.version
            fully_have = $full
            download_mb = [math]::Round($needBytes / $script:BytesPerMb, 1)
            extract_mb  = [math]::Round($extractThis / $script:BytesPerMb, 1)
            extract_known = $extractKnown
            changed     = @($needNames)
        })
    }

    return [pscustomobject]@{
        download_mb = [math]::Round($downloadBytes / $script:BytesPerMb, 1)
        extract_mb  = [math]::Round($extractBytes / $script:BytesPerMb, 1)
        peak_mb     = [math]::Round(($downloadBytes + $extractBytes) / $script:BytesPerMb, 1)
        final_mb    = [math]::Round($extractBytes / $script:BytesPerMb, 1)
        unknown_extract = $unknownExtract
        books       = $rows.ToArray()
    }
}

# Compatibility gate: the plan plus a safety reserve must fit the free space of
# the install volume, measured in MB.
function Test-DiskPlanCompatibility {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$Plan,
        [Parameter(Mandatory = $true)][double]$FreeMb,
        [double]$ReserveMb = 512
    )

    $required = [math]::Round($Plan.peak_mb + $ReserveMb, 1)
    $ok = $FreeMb -ge $required
    $unknown = ((Get-PropertyNames $Plan) -contains 'unknown_extract') -and [bool]$Plan.unknown_extract
    $msg = if ($ok) {
        "磁盘充足: 需要 $required MB (峰值 $($Plan.peak_mb) + 预留 $ReserveMb)，可用 $FreeMb MB"
    }
    else {
        "磁盘不足: 需要 $required MB (峰值 $($Plan.peak_mb) + 预留 $ReserveMb)，可用 $FreeMb MB，缺少 $([math]::Round($required - $FreeMb,1)) MB"
    }
    if ($unknown) {
        $msg += '；注意: 解压占用未知(发布资源里缺少 wcp-wordbook.json)，上面的峰值只按下载量+预留估算，实际解压后仍可能占满磁盘'
    }
    return [pscustomobject]@{
        ok          = $ok
        required_mb = $required
        free_mb     = $FreeMb
        reserve_mb  = $ReserveMb
        extract_unknown = $unknown
        shortfall_mb = if ($ok) { 0.0 } else { [math]::Round($required - $FreeMb, 1) }
        message     = $msg
    }
}

function Read-HubState {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{ schema = 2; layout = 2; game = ''; wordbooks = [pscustomobject]@{} }
    }
    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return [pscustomobject]@{ schema = 2; layout = 2; game = ''; wordbooks = [pscustomobject]@{} }
    }
    $state = $raw | ConvertFrom-Json
    $names = Get-PropertyNames $state
    if (($names -contains 'schema' -and [int]$state.schema -ne 2) -or
        ($names -contains 'layout' -and [int]$state.layout -ne 2)) {
        # Layout 1 wrote language assets into shared legacy directories.  Treat
        # it as empty so the first run after this change re-materializes every
        # selected resource under packs/<language>/.
        return [pscustomobject]@{ schema = 2; layout = 2; game = ''; wordbooks = [pscustomobject]@{} }
    }
    return $state
}

function Get-InstalledWordbooks {
    param($State)
    if (-not $State -or -not $State.wordbooks) { return [pscustomobject]@{} }
    return $State.wordbooks
}

# Only a pack recorded by this Hub, in its own language directory, may be removed.
# Resolve the final path before the caller issues any recursive removal.
function Get-HubPackRemovalTarget {
    param([Parameter(Mandatory = $true)]$Wordbook,
          [Parameter(Mandatory = $true)]$InstalledState,
          [Parameter(Mandatory = $true)][string]$PacksRoot)
    $id = [string]$Wordbook.id
    $lang = [string]$Wordbook.language
    if ($lang -cnotmatch '^[a-z]{2,5}$' -or
        (Get-PropertyNames $InstalledState) -notcontains $id) {
        throw "词书不属于当前 Hub 安装记录: $id"
    }
    $root = [IO.Path]::GetFullPath($PacksRoot).TrimEnd('\', '/')
    $target = [IO.Path]::GetFullPath((Join-Path $root $lang))
    if (Test-Path -LiteralPath $root) {
        $rootItem = Get-Item -LiteralPath $root -Force
        if (-not $rootItem.PSIsContainer -or
            ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "词书根目录不是普通目录，拒绝卸载: $root"
        }
    }
    if (-not [string]::Equals([IO.Path]::GetDirectoryName($target), $root,
                             [StringComparison]::OrdinalIgnoreCase)) {
        throw "词书目录越界，拒绝卸载: $target"
    }
    if (Test-Path -LiteralPath $target) {
        $item = Get-Item -LiteralPath $target -Force
        if (-not $item.PSIsContainer -or
            ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "词书目录不是普通目录，拒绝卸载: $target"
        }
        $linked = Get-ChildItem -LiteralPath $target -Recurse -Force -Attributes ReparsePoint -ErrorAction Stop |
            Select-Object -First 1
        if ($linked) { throw "词书目录含链接，拒绝卸载: $target" }
        $manifestPath = Join-Path $target 'manifest.json'
        if (-not (Test-Path -LiteralPath $manifestPath)) {
            throw "词书清单缺失，拒绝卸载: $target"
        }
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([string]$manifest.language -cne $lang -or
            [string]$manifest.profile_id -cne [string]$Wordbook.profile_id) {
            throw "词书清单身份不符，拒绝卸载: $target"
        }
    }
    return $target
}

function Sync-WordAudioMirror {
    # 单词音频兼容层：把 pack 里的单词音频镜像到游戏原生目录
    # （%USERPROFILE%\AppData\LocalLow\WCP\vocabulary）。
    #
    # 为什么需要：游戏的 VocabularyAudioPlayer 只读那个目录（引擎自带路径，
    # 不是本安装器或插件的约定）。该目录为空时，宿主未接管（首次读档中 /
    # 未重启游戏 / 未激活）发音会静默回退成游戏的英语 AI 语音——只在
    # 用户机暴露、开发机因历史副本而正常。规则对所有语言一致，无语言分支；
    # 只覆盖同名文件，不清理其它内容（该目录为多语言共享），保留名文件
    # 镜像失败即跳过。
    #
    # 2026-09-17 评估过"硬链接省 669 MB 冗余"：技术上可行，但该目录与游戏官方
    # 语音包共用，链接一旦被游戏就地覆写就会反向污染 pack 源文件 → 按兼容优先否决，
    # 保持复制。（测量数据见 docs/TASKS.md P1-18。）
    #
    # 返回实际复制/覆盖的文件数；源目录缺失或目标不可写时返回 -1
    # （调用方只提示，不视为安装失败）。
    param(
        [Parameter(Mandatory = $true)][string]$SourceDir,
        [Parameter(Mandatory = $true)][string]$VocabDir
    )
    if (-not (Test-Path -LiteralPath $SourceDir)) { return -1 }
    try {
        if (-not (Test-Path -LiteralPath $VocabDir)) {
            New-Item -ItemType Directory -Path $VocabDir -Force | Out-Null
        }
        $mirrored = 0
        foreach ($mp3 in [IO.Directory]::EnumerateFiles($SourceDir, '*.mp3', [IO.SearchOption]::AllDirectories)) {
            try {
                # 只允许"复制"，绝不用硬链接/符号链接（2026-09-17 实测后否决）：
                # 本目录同时是游戏官方语音包自己的读写目录，链接会让游戏对同名文件的
                # 就地覆写穿透到 pack 源文件（= 词书资源被游戏语音污染，且磁盘核对只数
                # 文件数、查不出来）。代价是 9 语言约 669 MB 冗余，换取源文件不可被外部改写。
                # 守卫：tests/test_hub.ps1 用例「镜像：写镜像侧不影响 pack 源文件」。
                [IO.File]::Copy($mp3, (Join-Path $VocabDir ([IO.Path]::GetFileName($mp3))), $true)
                $mirrored++
            } catch { }
        }
        return $mirrored
    } catch { return -1 }
}

# P1-9 — 磁盘健康核对（-Update 前运行；纯只读，绝不写/删任何文件）。
#
# hub-state.json 只记录「当时下载的资产 sha256」；用户手动删文件、解压被杀软
# 隔离、磁盘故障都会让磁盘偏离 state 而 -Update 察觉不到（P1-9 实证：本机
# 8 语言 pack 音频目录为空但 state 全记 sha256 一致）。这里对每个已安装词书
# 按 pack manifest 自证做健康检查：
#   1. pack 骨架: manifest.json / db/meaning.sqlite(SQLite 头) / db/repair.tsv / db/sentences.json
#   2. 词表自证: repair.tsv 的 `row<TAB>pron<TAB>` 行数 == manifest.counts.pron
#      （repair 是 pack 的唯一生成源；9 语言 2026-09-17 实测全等，行数漂移=内容损坏）
#   3. 音频抽样: 只对 catalog 带 word_audio 资产的语言检查 packs/<lang>/audio/word
#      的 mp3 计数 >= 词数*0.95（迁移期共享目录形态不强制，避免误伤）。
# 任何异常按「该词书不健康」处理（fail-closed）。返回不健康词书 id 数组。
function Test-WordbookDiskHealth {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$Catalog,
        [Parameter(Mandatory = $true)]$InstalledState,
        [Parameter(Mandatory = $true)][string]$PacksRoot
    )

    $unhealthy = New-Object System.Collections.Generic.List[string]
    foreach ($wb in @($Catalog.wordbooks)) {
        $bookId = [string]$wb.id
        $names = Get-PropertyNames $InstalledState
        if ($names -notcontains $bookId) { continue }
        $lang = [string]$wb.language
        $packDir = Join-Path $PacksRoot $lang
        try {
            if (-not (Test-Path -LiteralPath $packDir)) { throw 'pack 目录缺失' }
            $manifestPath = Join-Path $packDir 'manifest.json'
            if (-not (Test-Path -LiteralPath $manifestPath)) { throw '缺 manifest.json' }
            $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $expected = 0
            if ($manifest -and $manifest.counts -and
                (Get-PropertyNames $manifest.counts) -contains 'pron') {
                $expected = [int]$manifest.counts.pron
            }
            if ($expected -le 0) { $expected = [int]$wb.word_count }
            if ($expected -le 0) { throw 'manifest 与 catalog 都没有词数记录' }

            $dbDir = Join-Path $packDir 'db'
            foreach ($name in @('meaning.sqlite', 'repair.tsv', 'sentences.json')) {
                if (-not (Test-Path -LiteralPath (Join-Path $dbDir $name))) {
                    throw ('缺 db/' + $name)
                }
            }
            $head = New-Object byte[] 16
            $fs = [IO.File]::OpenRead((Join-Path $dbDir 'meaning.sqlite'))
            try { [void]$fs.Read($head, 0, 16) } finally { $fs.Dispose() }
            if ([Text.Encoding]::ASCII.GetString($head) -ne 'SQLite format 3' + [char]0) {
                throw 'meaning.sqlite 不是 SQLite 库'
            }

            $pronPrefix = 'row' + [char]9 + 'pron' + [char]9
            $actual = 0
            foreach ($line in [IO.File]::ReadLines((Join-Path $dbDir 'repair.tsv'))) {
                if ($line -ne $null -and $line.StartsWith($pronPrefix)) { $actual++ }
            }
            if ($actual -ne $expected) {
                throw ('词表行数 ' + $actual + ' 与 manifest 记录 ' + $expected + ' 不符')
            }

            $wordAsset = $null
            foreach ($a in @($wb.assets)) {
                if ([string]$a.kind -eq 'word_audio') { $wordAsset = $a; break }
            }
            if ($wordAsset) {
                $wordDir = Join-Path $packDir 'audio\word'
                $mp3 = 0
                if (Test-Path -LiteralPath $wordDir) {
                    $mp3 = @([IO.Directory]::EnumerateFiles($wordDir, '*.mp3')).Count
                }
                $minMp3 = [math]::Floor($expected * 0.95)
                if ($mp3 -lt $minMp3) {
                    throw ('单词音频 ' + $mp3 + ' 个低于期望 ' + $minMp3 + '（词数*0.95）')
                }
            }
            Write-Verbose ($bookId + ': 健康（' + $actual + ' 词）')
        } catch {
            Write-Host ('  磁盘核对: {0} 不健康（{1}）→ 本次将全量重下' -f $bookId, $_.Exception.Message) -ForegroundColor Yellow
            $unhealthy.Add($bookId)
        }
    }
    return $unhealthy.ToArray()
}

function Test-ModDiskHealth([string]$gameRoot) {
    # Mod 本体物理健康核对（安装/更新前运行）。
    #
    # 背景：hub-state.json 只记录「当时下载的 mods 载荷 sha256」，安装器据此判断
    # 「已是最新」并跳过。可一旦磁盘上的插件被改名（2026-09-21 实机：A/B 测试
    # 遗留 WcpHost.dll.disabled）、被杀软隔离或写坏成 0 字节，状态文件仍旧自洽，
    # 安装器永远不自愈 —— 游戏侧表现为旧插件打印「WcpHost 已接管 X 语，旧词表插件
    # 不再打补丁」主动让渡，而宿主实际没加载，整个词典 Hook 链真空，查词面板对
    # 所有受管语言回退成游戏原生「本地暂未收录这个单词」。
    #
    # 检查三层，任何一层不过都返回 $false（调用方据此强制重新物化 mods 载荷）：
    #   1. 核心三件套（WcpHost / CustomSlotsMod / BookNameMod）必须存在且非 0 字节。
    #      只查这三件：它们是与语言无关的基础设施，新语言接入不需要改本函数。
    #   2. 顺带自愈被「改名禁用」的插件：同名 .disabled/.off/.bak 目标缺失时改名回正，
    #      目标已存在时删掉遗留副本（旧语言插件也在覆盖范围内，保持同规则）。
    #   3. 自愈后复检三件套，仍缺则判定不健康。
    if (-not $gameRoot) { return $true }
    $pluginsRoot = Join-Path (Join-Path $gameRoot 'BepInEx') 'plugins'
    if (-not (Test-Path -LiteralPath $pluginsRoot)) { return $false }

    # 2. 先扫遗留的「改名禁用」副本（对任意插件生效，不只核心三件套）。
    foreach ($stray in @([IO.Directory]::EnumerateFiles($pluginsRoot, '*.dll.disabled', [IO.SearchOption]::TopDirectoryOnly)) +
                        @([IO.Directory]::EnumerateFiles($pluginsRoot, '*.dll.off', [IO.SearchOption]::TopDirectoryOnly)) +
                        @([IO.Directory]::EnumerateFiles($pluginsRoot, '*.dll.bak', [IO.SearchOption]::TopDirectoryOnly))) {
        $liveName = [IO.Path]::GetFileName($stray)
        foreach ($suffix in @('.disabled', '.off', '.bak')) {
            if ($liveName.EndsWith($suffix, [StringComparison]::OrdinalIgnoreCase)) {
                $liveName = $liveName.Substring(0, $liveName.Length - $suffix.Length)
                break
            }
        }
        $livePath = Join-Path $pluginsRoot $liveName
        if (Test-Path -LiteralPath $livePath) {
            Remove-Item -LiteralPath $stray -Force -ErrorAction SilentlyContinue
            Write-Host ('  mod 物理自愈: 清理遗留副本 ' + [IO.Path]::GetFileName($stray)) -ForegroundColor DarkGray
        } else {
            try {
                Move-Item -LiteralPath $stray -Destination $livePath -Force -ErrorAction Stop
                Write-Host ('  mod 物理自愈: 已把 ' + [IO.Path]::GetFileName($stray) + ' 恢复为 ' + $liveName) -ForegroundColor Yellow
            } catch { }
        }
    }

    # 1/3. 核心三件套必须在位且非 0 字节。
    foreach ($core in @('WcpHost.dll', 'CustomSlotsMod.dll', 'BookNameMod.dll')) {
        $path = Join-Path $pluginsRoot $core
        if (-not (Test-Path -LiteralPath $path)) {
            Write-Host ('  mod 磁盘核对: 缺少核心插件 ' + $core) -ForegroundColor Yellow
            return $false
        }
        $item = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
        if (-not $item -or $item.Length -eq 0) {
            Write-Host ('  mod 磁盘核对: 核心插件 ' + $core + ' 为 0 字节') -ForegroundColor Yellow
            return $false
        }
    }
    return $true
}

Export-ModuleMember -Function Import-WordbookCatalog, Assert-WordbookCatalog, `
    Get-WordbookById, Resolve-WordbookSelection, Get-WordbookAssetDiff, `
    Test-WordbookInstalledFully, New-DiskPlan, Test-DiskPlanCompatibility, `
    Read-HubState, Get-InstalledWordbooks, Get-ExtractMb, Test-ExtractKnown, `
    Get-HubCatalogRows, Get-InstalledBookIds, Resolve-InteractivePick, Sync-WordAudioMirror, Test-WordbookDiskHealth, Test-ModDiskHealth, Get-HubPackRemovalTarget
