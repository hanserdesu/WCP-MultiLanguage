# Install-WCP-Wordbooks.ps1 — unified WCP wordbook installer CLI.
#
# Reads hub/catalog.json (bundled or fetched from GitHub), lets the user pick
# wordbooks, computes a peak-disk compatibility plan, then downloads and
# verifies each asset into the game's data directory under a per-language
# namespace. -Update re-downloads only assets whose sha256 differs from the
# installed state recorded in hub-state.json.
#
# Usage:
#   .\Install-WCP-Wordbooks.ps1 -List
#   .\Install-WCP-Wordbooks.ps1 -Plan -Books fr,ja
#   .\Install-WCP-Wordbooks.ps1 -All
#   .\Install-WCP-Wordbooks.ps1 -Books fr -Update
#   .\Install-WCP-Wordbooks.ps1 -List -Offline

param(
    [switch]$List,
    [switch]$Plan,
    [switch]$Update,
    [switch]$All,
    [string[]]$Books,
    [string]$CatalogPath,
    [string]$GameDir,
    [string]$StatePath,
    [double]$ReserveMb = 512,
    [switch]$Yes,
    [switch]$Offline,
    [string]$GitHubOwner = 'hanserdesu'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module (Join-Path $here 'WordbookHub.psm1') -Force

function Get-PropertyNames($Object) {
    if ($null -eq $Object) { return @() }
    return @($Object.PSObject.Properties | ForEach-Object { $_.Name })
}

# ---------- locate game ----------
function Get-GameRoot {
    if ($GameDir) { return $GameDir }
    $candidates = @()
    foreach ($driveRoot in @('C:\', 'D:\', 'E:\', 'F:\')) {
        $p = Join-Path $driveRoot 'Steam\steamapps\common\WCP-WordGirlgriend'
        if (Test-Path -LiteralPath $p) { $candidates += $p }
    }
    $logPath = Join-Path $env:USERPROFILE 'AppData\LocalLow\WCP\wcp\Player.log'
    if (Test-Path -LiteralPath $logPath) {
        try {
            foreach ($line in (Get-Content -LiteralPath $logPath -TotalCount 40 -Encoding UTF8)) {
                if ($line -match '([A-Z]:\\[^\r\n]*WCP-WordGirlgriend)') {
                    $candidates += $Matches[1]; break
                }
            }
        } catch { }
    }
    if ($candidates.Count -eq 0) { throw '未找到游戏目录，请用 -GameDir 指定' }
    return $candidates[0]
}

$data = Join-Path $env:USERPROFILE 'AppData\LocalLow\WCP\wcp'
$packsRoot = Join-Path (Split-Path -Parent $data) 'packs'
$statePathResolved = if ($StatePath) { $StatePath } else { Join-Path $data 'hub-state.json' }
$catalogPathResolved = if ($CatalogPath) { $CatalogPath } else { Join-Path $here 'catalog.json' }

# ---------- GitHub catalog discovery ----------
# A release may optionally carry a wcp-wordbook.json/release-manifest.json
# asset.  When absent, the installer can still infer the two audio assets from
# their names and GitHub's sha256 digest.  This makes adding a language a
# repository-resource change; the host and its tests do not enumerate languages.
function Get-GitHubJson([string]$url) {
    $headers = @{
        'User-Agent' = 'WCP-WordbookHub/1.0'
        'Accept' = 'application/vnd.github+json'
    }
    $token = [Environment]::GetEnvironmentVariable('GITHUB_TOKEN')
    if (-not [string]::IsNullOrWhiteSpace($token)) {
        $headers['Authorization'] = 'Bearer ' + $token
    }
    return Invoke-RestMethod -Uri $url -Method Get -Headers $headers -UseBasicParsing -TimeoutSec 25
}

function Get-ReleaseAssetSha($remote, $seed, [string]$declaredSha) {
    $digest = [string](Get-FieldOr $remote 'digest' '')
    if ($digest -match '^sha256:([0-9a-fA-F]{64})$') { return $Matches[1].ToLowerInvariant() }
    if ($declaredSha -match '^[0-9a-fA-F]{64}$') { return $declaredSha.ToLowerInvariant() }
    foreach ($old in @(Get-FieldOr $seed 'assets' @())) {
        if ([string](Get-FieldOr $old 'name' '') -eq [string]$remote.name -and
            [int64](Get-FieldOr $old 'size' 0) -eq [int64]$remote.size -and
            [string](Get-FieldOr $old 'sha256' '') -match '^[0-9a-fA-F]{64}$') {
            return ([string]$old.sha256).ToLowerInvariant()
        }
    }
    return $null
}

# Reads an optional field without tripping -StrictMode.  A release manifest is
# authored per language repository, so every field except id must be optional:
# a minimal manifest must never take a whole language's discovery offline.
function Get-FieldOr($Object, [string]$Name, $Fallback) {
    if (-not $Object) { return $Fallback }
    if ((Get-PropertyNames $Object) -notcontains $Name) { return $Fallback }
    $value = $Object.$Name
    if ($null -eq $value) { return $Fallback }
    return $value
}

function Get-ManifestFromRelease($release) {
    foreach ($a in @(Get-FieldOr $release 'assets' @())) {
        if ([string](Get-FieldOr $a 'name' '') -notmatch '^(wcp-wordbook|wordbook-manifest|release-manifest)\.json$') { continue }
        try { return Get-GitHubJson ([string](Get-FieldOr $a 'browser_download_url' '')) } catch { return $null }
    }
    return $null
}

function New-RemoteWordbook($seed, $release, [string]$repoName) {
    if (-not $release) { return $null }
    $manifest = Get-ManifestFromRelease $release
    $manifestBooks = Get-FieldOr $manifest 'wordbooks' $null
    if ($manifestBooks) {
        $seedId = [string](Get-FieldOr $seed 'id' '')
        foreach ($candidate in @($manifestBooks)) {
            if ([string](Get-FieldOr $candidate 'repo' '') -ieq $repoName -or
                [string](Get-FieldOr $candidate 'id' '') -ieq $seedId) {
                $manifest = $candidate
                break
            }
        }
    }

    $id = [string](Get-FieldOr $manifest 'id' (Get-FieldOr $seed 'id' ''))
    $language = [string](Get-FieldOr $manifest 'language' (Get-FieldOr $seed 'language' $id))
    if ([string]::IsNullOrWhiteSpace($id)) { return $null }
    $display = [string](Get-FieldOr $manifest 'display_name' (Get-FieldOr $seed 'display_name' ($language + ' 词书')))
    $prefix = [string](Get-FieldOr $manifest 'es3_prefix' (Get-FieldOr $seed 'es3_prefix' $id))
    $count = [int](Get-FieldOr $manifest 'word_count' (Get-FieldOr $seed 'word_count' 0))
    $fingerprint = [string](Get-FieldOr $manifest 'fingerprint_sha256' (Get-FieldOr $seed 'fingerprint_sha256' ''))
    $manifestDisk = Get-FieldOr $manifest 'disk' $null
    $seedDisk = Get-FieldOr $seed 'disk' $null
    $extract = [double](Get-FieldOr $manifestDisk 'extract_mb' (Get-FieldOr $seedDisk 'extract_mb' 0))

    $assets = New-Object System.Collections.Generic.List[object]
    $manifestAssets = Get-FieldOr $manifest 'assets' $null
    if ($manifestAssets) {
        foreach ($a in @($manifestAssets)) {
            $assetName = [string](Get-FieldOr $a 'name' '')
            if ([string]::IsNullOrWhiteSpace($assetName)) { continue }
            $remote = @(Get-FieldOr $release 'assets' @() | Where-Object { [string]$_.name -eq $assetName }) | Select-Object -First 1
            if (-not $remote) { continue }
            $sha = Get-ReleaseAssetSha $remote $seed ([string](Get-FieldOr $a 'sha256' ''))
            if (-not $sha) { continue }
            $assets.Add([pscustomobject]@{
                kind = [string](Get-FieldOr $a 'kind' 'pack')
                name = [string]$remote.name
                size = [int64]$remote.size
                sha256 = $sha
                url = [string]$remote.browser_download_url
            })
        }
    }
    if ($assets.Count -eq 0) {
        foreach ($remote in @(Get-FieldOr $release 'assets' @())) {
            $name = [string]$remote.name
            if ($name -notmatch '\.(zip|7z|tar|gz)$') { continue }
            $kind = if ($name -match '(?i)sentence|example') { 'sentence_audio' } elseif ($name -match '(?i)word|audio') { 'word_audio' } else { 'payload' }
            $sha = Get-ReleaseAssetSha $remote $seed $null
            if (-not $sha) { continue }
            $assets.Add([pscustomobject]@{
                kind = $kind
                name = $name
                size = [int64]$remote.size
                sha256 = $sha
                url = [string]$remote.browser_download_url
            })
        }
    }

    $status = if ($assets.Count -gt 0) { 'available' } else { 'pending_release' }
    return [pscustomobject]@{
        id = $id
        status = $status
        language = $language
        display_name = $display
        repo = $repoName
        release_tag = [string](Get-FieldOr $release 'tag_name' '')
        version = [string](Get-FieldOr $release 'tag_name' '')
        word_count = $count
        fingerprint_sha256 = $fingerprint
        es3_prefix = $prefix
        disk = [pscustomobject]@{ extract_mb = $extract }
        assets = $assets.ToArray()
    }
}

function Get-GitHubCatalog($base, [string]$owner) {
    $repos = Get-GitHubJson ("https://api.github.com/users/{0}/repos?per_page=100&sort=updated" -f $owner)
    $repoRows = @($repos | Where-Object {
        [string](Get-FieldOr $_ 'full_name' '') -match ('^' + [regex]::Escape($owner) + '/(?:japanese|WCP-.+-Wordbook)$')
    })
    $byRepo = @{}
    foreach ($wb in @($base.wordbooks)) { $byRepo[[string]$wb.repo] = $wb }
    foreach ($repo in $repoRows) {
        $repoName = [string](Get-FieldOr $repo 'full_name' '')
        $seed = if ($byRepo.ContainsKey($repoName)) { $byRepo[$repoName] } else {
            $rawId = ([string](Get-FieldOr $repo 'name' '') -replace '^WCP-', '' -replace '-Wordbook$', '').ToLowerInvariant()
            [pscustomobject]@{
                id = $rawId; status = 'pending_release'; language = $rawId
                display_name = $rawId + ' 词书'; repo = $repoName; release_tag = ''
                version = ''; word_count = 0; fingerprint_sha256 = ''; es3_prefix = $rawId
                disk = [pscustomobject]@{ extract_mb = 0 }; assets = @()
            }
    }
    try {
            # A wordbook repo may publish a small core release after its
            # resource release.  Probe the catalog-pinned resource tag and
            # latest release, then keep the candidate with the richest asset
            # set. This lets resource-only updates flow from GitHub without
            # making the installer depend on release ordering.
            $candidates = New-Object System.Collections.Generic.List[object]
            $pinnedTag = [string](Get-FieldOr $seed 'release_tag' '')
            if (-not [string]::IsNullOrWhiteSpace($pinnedTag)) {
                try {
                    $tagUrl = "https://api.github.com/repos/{0}/releases/tags/{1}" -f `
                        $repoName, [Uri]::EscapeDataString($pinnedTag)
                    [void]$candidates.Add((Get-GitHubJson $tagUrl))
                } catch { Write-Verbose ("GitHub 词书固定资源版本不可用 {0}/{1}: {2}" -f $repoName, $pinnedTag, $_.Exception.Message) }
            }
            try {
                $latest = Get-GitHubJson ("https://api.github.com/repos/{0}/releases/latest" -f $repoName)
                if (-not @($candidates | Where-Object { [string](Get-FieldOr $_ 'tag_name' '') -eq [string](Get-FieldOr $latest 'tag_name' '') })) {
                    [void]$candidates.Add($latest)
                }
            } catch { Write-Verbose ("GitHub 词书 latest 不可用 {0}: {1}" -f $repoName, $_.Exception.Message) }

            $best = $null
            $bestAssetCount = -1
            foreach ($candidate in @($candidates)) {
                $remote = New-RemoteWordbook $seed $candidate $repoName
                if (-not $remote) { continue }
                $assetCount = @($remote.assets).Count
                if ($assetCount -gt $bestAssetCount -or
                    ($assetCount -eq $bestAssetCount -and $best -ne $null)) {
                    $best = $remote
                    $bestAssetCount = $assetCount
                }
            }
            if ($best) { $byRepo[$repoName] = $best }
        } catch {
            Write-Verbose ("GitHub 词书发现跳过 {0}: {1}" -f $repoName, $_.Exception.Message)
        }
    }
    $rows = @($byRepo.Values | Sort-Object id)
    $result = [pscustomobject]@{ schema = 1; updated = (Get-Date).ToString('yyyy-MM-dd'); wordbooks = $rows }
    Assert-WordbookCatalog -Catalog $result
    return $result
}

$catalog = Import-WordbookCatalog -Path $catalogPathResolved
$cachePath = Join-Path $data 'hub-catalog-cache.json'
if (-not $Offline) {
    try {
        if (-not (Test-Path -LiteralPath $data)) { New-Item -ItemType Directory -Path $data -Force | Out-Null }
        $catalog = Get-GitHubCatalog -base $catalog -owner $GitHubOwner
        $catalog | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $cachePath -Encoding UTF8
        Write-Verbose '已从 GitHub 刷新词书目录'
    } catch {
        Write-Warning ('GitHub 目录刷新失败，使用随包目录: ' + $_.Exception.Message)
        if (Test-Path -LiteralPath $cachePath) {
            try { $catalog = Import-WordbookCatalog -Path $cachePath } catch { Write-Warning '缓存目录无效，继续使用随包目录' }
        }
    }
}
$state = Read-HubState -Path $statePathResolved
$state.schema = 2
$state.layout = 2
$installed = Get-InstalledWordbooks -State $state

function Show-Catalog {
    Write-Host ''
    Write-Host '== 可用词书 ==' -ForegroundColor Cyan
    foreach ($row in @(Get-HubCatalogRows -Catalog $catalog -InstalledState $installed)) {
        $installedMark = if ($row.installed) { '[已安装]' } else { '[      ]' }
        $size = if ($row.extract_known) { '解压 {0} MB' -f $row.extract_mb } else { '解压 未知' }
        Write-Host ('  {0,2}. {1} {2,-4} {3}  {4} 词  {5}  {6}  {7}' -f `
            $row.index, $installedMark, $row.id, $row.display_name, $row.word_count, $row.version, $size, $row.status)
    }
    Write-Host ''
}

function Get-FreeMb([string]$path) {
    $drive = [IO.Path]::GetPathRoot((Resolve-Path -LiteralPath $path).Path)
    $driveName = $drive.Substring(0, 1)
    $d = Get-PSDrive -Name $driveName
    return [math]::Round($d.Free / 1MB, 1)
}

function Get-Sha256Hex([string]$path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [IO.File]::OpenRead($path)
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($stream) { $stream.Dispose() }
        if ($sha) { $sha.Dispose() }
    }
}

function Expand-HubZip([string]$zipPath, [string]$dest) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (-not (Test-Path -LiteralPath $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
    [IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $dest, $true)
}

function Merge-SlotSeed([string]$source) {
    $slotSeed = Join-Path $data 'WcpCustomSlots.seed.json'
    if (-not (Test-Path -LiteralPath $slotSeed)) {
        Copy-Item -LiteralPath $source -Destination $slotSeed -Force
        return
    }

    $current = Get-Content -LiteralPath $slotSeed -Raw -Encoding UTF8 | ConvertFrom-Json
    $incoming = Get-Content -LiteralPath $source -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $current -or $null -eq $incoming -or $null -eq $incoming.slots) {
        throw 'slot_manifest 根对象或 slots 无效'
    }

    $rows = New-Object System.Collections.Generic.List[object]
    foreach ($row in @($current.slots)) { if ($rows.Count -lt 20) { [void]$rows.Add($row) } }
    while ($rows.Count -lt 20) {
        $n = $rows.Count + 1
        [void]$rows.Add([pscustomobject]@{
            number = $n; id = ''; name = ''; language = ''; owner = 'external'
            managed = $false; nativeSlot = 0; words = @()
        })
    }

    foreach ($row in @($incoming.slots)) {
        $props = Get-PropertyNames $row
        if (($props -notcontains 'managed') -or -not [bool]$row.managed) { continue }
        if (($props -notcontains 'words') -or @($row.words).Count -lt 5) { continue }

        $target = -1
        if ($props -contains 'id' -and -not [string]::IsNullOrWhiteSpace([string]$row.id)) {
            for ($i = 0; $i -lt $rows.Count; $i++) {
                if ([string]$rows[$i].id -eq [string]$row.id) { $target = $i; break }
            }
        }
        if ($target -lt 0) {
            for ($i = 0; $i -lt $rows.Count; $i++) {
                $existingWords = if ((Get-PropertyNames $rows[$i]) -contains 'words') { @($rows[$i].words) } else { @() }
                if ($existingWords.Count -lt 5) { $target = $i; break }
            }
        }
        if ($target -ge 0) {
            $row.number = $target + 1
            $rows[$target] = $row
        }
    }

    $merged = [pscustomobject]@{
        schema = 1
        selected = if ((Get-PropertyNames $current) -contains 'selected') { [int]$current.selected } else { 0 }
        slots = $rows.ToArray()
    }
    $merged | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $slotSeed -Encoding UTF8
}

function Save-HubState {
    $state.schema = 2
    $state.layout = 2
    $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statePathResolved -Encoding UTF8
}

# ---------- main ----------
if ($List) { Show-Catalog; exit 0 }

$game = Get-GameRoot
if (-not (Test-Path -LiteralPath $data)) { New-Item -ItemType Directory -Path $data -Force | Out-Null }

$rows = @(Get-HubCatalogRows -Catalog $catalog -InstalledState $installed)
if ($Books -or $All) {
    $selection = Resolve-WordbookSelection -Catalog $catalog -Ids $Books -All:$All
} else {
    # 同一个页面里列出现有词书，用户输入编号即可选择；-Update 不带 -Books 时
    # 默认就是"更新我已经装过的那些"，避免必须记 id。
    $installedIds = @(Get-InstalledBookIds -Catalog $catalog -InstalledState $installed)
    if ($Update -and $installedIds.Count -eq 0) {
        Write-Host '没有已安装的词书可更新。' -ForegroundColor Yellow
        Show-Catalog
        exit 0
    }
    $defaultIds = if ($Update) { $installedIds } else { @() }
    Show-Catalog
    $pick = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $hint = if ($Update) {
            ('请输入要更新的编号 (逗号分隔; 回车=已安装的 {0} 本; q=取消)' -f $defaultIds.Count)
        } else {
            '请输入要安装的编号 (逗号分隔; all=全部可安装; q=取消)'
        }
        $answer = Read-Host $hint
        try { $pick = Resolve-InteractivePick -Rows $rows -Answer $answer -DefaultIds $defaultIds; break }
        catch { Write-Host ('  ' + $_.Exception.Message) -ForegroundColor Yellow }
    }
    if (-not $pick) { throw '选择无效，已退出安装。' }
    if ($pick.cancelled) { Write-Host '已取消'; exit 0 }
    $selection = Resolve-WordbookSelection -Catalog $catalog -Ids $pick.ids
}
$state.game = $game
$diskPlan = New-DiskPlan -Wordbooks $selection -InstalledState $installed
$freeMb = Get-FreeMb $data
$compat = Test-DiskPlanCompatibility -Plan $diskPlan -FreeMb $freeMb -ReserveMb $ReserveMb

Write-Host ''
Write-Host '== 安装计划 ==' -ForegroundColor Cyan
foreach ($row in $diskPlan.books) {
    $status = if ($row.fully_have) { '已是最新' } else { '需下载' }
    Write-Host ('  {0,-4} {1}  下载 {2} MB  解压 {3} MB  {4}' -f $row.id, $row.version, $row.download_mb, $row.extract_mb, $status)
}
Write-Host ('  峰值磁盘: {0} MB   最终占用: {1} MB' -f $diskPlan.peak_mb, $diskPlan.final_mb)
Write-Host ('  {0}' -f $compat.message)
if (-not $compat.ok) { throw $compat.message }

if ($Plan) { exit 0 }

if (-not $Yes) {
    Write-Host ''
    $answer = Read-Host '确认安装? (y/n)'
    if ($answer -notin @('y', 'Y', 'yes', 'Yes')) { Write-Host '已取消'; exit 0 }
}

# 运行时补丁所有权登记（与日语一键安装器同一段逻辑）：按"资源确实就绪"判定受管语言，
# 写进 <游戏>\BepInEx\config\WcpHost.managed.txt。旧词表插件读到自己的语言在列时
# 整场不打补丁，运行时补丁只剩宿主一个所有者 —— 这是"俄语切日语后还出俄语"的根因修复。
function Update-ManagedLanguagesMarker([string]$gameRoot, [string]$packsDir) {
    $ready = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path -LiteralPath $packsDir)) { return $ready }
    foreach ($packDir in @(Get-ChildItem -LiteralPath $packsDir -Directory)) {
        $manifestPath = Join-Path $packDir.FullName 'manifest.json'
        if (-not (Test-Path -LiteralPath $manifestPath)) { continue }
        try { $m = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { continue }
        if (-not $m -or -not $m.language -or -not $m.resources) { continue }
        $need = New-Object System.Collections.Generic.List[string]
        foreach ($k in @('meaning_db', 'sentence_table', 'repair')) {
            if ($m.resources.$k) { $need.Add([string]$m.resources.$k) }
        }
        foreach ($b in @($m.resources.books)) { if ($b) { $need.Add([string]$b) } }
        $ok = $true
        foreach ($rel in $need) {
            if (-not (Test-Path -LiteralPath (Join-Path $packDir.FullName $rel))) { $ok = $false; break }
        }
        if ($ok) { $ready.Add([string]$m.language) }
    }
    $marker = Join-Path (Join-Path $gameRoot 'BepInEx') 'config'
    $marker = Join-Path $marker 'WcpHost.managed.txt'
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $marker) | Out-Null
    [IO.File]::WriteAllLines($marker, [string[]]$ready, (New-Object System.Text.UTF8Encoding($false)))
    return $ready
}

$totalAssets = 0
foreach ($wb in $selection) {
    $changedForCount = @(Get-WordbookAssetDiff -Wordbook $wb -InstalledState $installed)
    if ($Update) { $totalAssets += $changedForCount.Count }
    elseif (-not (Test-WordbookInstalledFully -Wordbook $wb -InstalledState $installed)) { $totalAssets += @($wb.assets).Count }
}
$done = 0
$errors = New-Object System.Collections.Generic.List[string]

foreach ($wb in $selection) {
    $ns = Join-Path $data ($wb.es3_prefix + '_hub_payload')
    $packRoot = Join-Path $packsRoot ([string]$wb.language)
    $changed = @(Get-WordbookAssetDiff -Wordbook $wb -InstalledState $installed)
    if ($changed.Count -eq 0 -and (Test-WordbookInstalledFully -Wordbook $wb -InstalledState $installed)) {
        Write-Host ('  {0}: 已是最新，跳过' -f $wb.id); continue
    }
    if (-not (Test-Path -LiteralPath $ns)) { New-Item -ItemType Directory -Path $ns -Force | Out-Null }

    $files = if ($Update) { $changed } else { @($wb.assets) }
    $succeeded = @{}
    foreach ($asset in $files) {
        $done++
        Write-Host ('  [{0}/{1}] {2}: {3}' -f $done, $totalAssets, $wb.id, $asset.name)
        $tmp = Join-Path $data ('hub_dl_' + [guid]::NewGuid().ToString('N'))
        try {
            $request = [Net.HttpWebRequest]::Create($asset.url)
            $request.Method = 'GET'
            $request.Timeout = 120000
            $request.ReadWriteTimeout = 120000
            $request.Proxy = [Net.WebRequest]::DefaultWebProxy
            if ($request.Proxy) { $request.Proxy.Credentials = [Net.CredentialCache]::DefaultCredentials }
            $response = $request.GetResponse()
            $stream = $response.GetResponseStream()
            $fs = [IO.File]::Create($tmp)
            $buf = New-Object byte[] 262144
            while (($n = $stream.Read($buf, 0, $buf.Length)) -gt 0) { $fs.Write($buf, 0, $n) }
            $fs.Dispose(); $stream.Dispose(); $response.Dispose()
            $actual = Get-Sha256Hex $tmp
            if ($actual -ne ([string]$asset.sha256).ToLowerInvariant()) {
                throw ('SHA-256 不匹配: ' + $asset.name + ' 期望 ' + $asset.sha256 + ' 实际 ' + $actual)
            }
            if ($asset.kind -in @('word_audio', 'sentence_audio')) {
                $dest = Join-Path (Join-Path $packRoot 'audio') ($asset.kind -replace '_audio$', '')
                Expand-HubZip $tmp $dest
            } elseif ($asset.kind -eq 'slot_manifest') {
                # The custom-slot plugin owns the logical 20-row catalog.  Keep
                # the seed outside language-specific payload directories so the
                # same installer can service any selected book without making
                # the language packs depend on one another.
                Merge-SlotSeed $tmp
            } elseif ($asset.kind -eq 'pack' -and
                      [string]$asset.name -match '(?i)\.(zip|7z|tar|gz)$') {
                $dest = $packRoot
                if (-not (Test-Path -LiteralPath $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
                Expand-HubZip $tmp $dest
            } elseif ($asset.kind -eq 'payload' -and
                      [string]$asset.name -match '(?i)\.(zip|7z|tar|gz)$') {
                $dest = Join-Path $ns 'payload'
                Expand-HubZip $tmp $dest
            } else {
                Copy-Item -LiteralPath $tmp -Destination (Join-Path $ns $asset.name) -Force
            }
            Remove-Item -LiteralPath $tmp -Force
            $succeeded[[string]$asset.name] = $asset
        } catch {
            $errors.Add($wb.id + '/' + $asset.name + ': ' + $_.Exception.Message)
            if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
            continue
        }
    }
    # Record only assets that are known to have passed download/hash/install.
    # A failed asset must remain absent from state so the next -Update retries it.
    $oldBook = $null
    if ((Get-PropertyNames $installed) -contains $wb.id) { $oldBook = $installed.$($wb.id) }
    $oldFiles = if ($oldBook -and $oldBook.files) { $oldBook.files } else { $null }
    $bookFiles = [pscustomobject]@{}
    foreach ($a in @($wb.assets)) {
        if ($succeeded.ContainsKey([string]$a.name)) {
            $bookFiles | Add-Member -NotePropertyName $a.name -NotePropertyValue ([pscustomobject]@{ sha256 = $a.sha256; size = $a.size })
        } elseif ($oldFiles -and (Get-PropertyNames $oldFiles) -contains $a.name) {
            $old = $oldFiles.$($a.name)
            if ([string]$old.sha256 -eq [string]$a.sha256) {
                $bookFiles | Add-Member -NotePropertyName $a.name -NotePropertyValue ([pscustomobject]@{ sha256 = $old.sha256; size = $old.size })
            }
        }
    }
    $complete = (@($wb.assets).Count -gt 0)
    foreach ($a in @($wb.assets)) {
        if ((Get-PropertyNames $bookFiles) -notcontains $a.name -or
            [string]$bookFiles.$($a.name).sha256 -ne [string]$a.sha256) { $complete = $false; break }
    }
    $version = if ($complete) { [string]$wb.version } elseif ($oldBook) { [string]$oldBook.version } else { '' }
    $entry = [pscustomobject]@{ version = $version; installed = (Get-Date).ToString('s'); files = $bookFiles }
    if (-not ((Get-PropertyNames $state.wordbooks) -contains $wb.id)) {
        $state.wordbooks | Add-Member -NotePropertyName $wb.id -NotePropertyValue $entry
    } else {
        $state.wordbooks.$($wb.id) = $entry
    }
    Save-HubState
}

Write-Host ''
$managedLangs = @(Update-ManagedLanguagesMarker -gameRoot $game -packsDir $packsRoot)
if ($managedLangs.Count -gt 0) {
    Write-Host ('宿主受管语言登记：' + ($managedLangs -join ', ')) -ForegroundColor DarkGray
} else {
    Write-Host '宿主受管语言登记：无（语言包资源未就绪时旧插件继续兜底）' -ForegroundColor DarkGray
}
if ($errors.Count -gt 0) {
    Write-Host ('完成，但 {0} 个资源失败:' -f $errors.Count) -ForegroundColor Yellow
    foreach ($e in $errors) { Write-Host ('  ' + $e) -ForegroundColor Yellow }
    exit 1
}
Write-Host '全部完成。' -ForegroundColor Green
