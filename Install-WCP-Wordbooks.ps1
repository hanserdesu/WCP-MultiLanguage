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
    [string]$DataRoot,
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

$wcpRoot = if ($DataRoot) { $DataRoot } else { Join-Path $env:USERPROFILE 'AppData\LocalLow\WCP' }
$data = Join-Path $wcpRoot 'wcp'
$packsRoot = Join-Path $wcpRoot 'packs'
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
    # Discovery is keyed by wordbook id, not by repository.  A single release
    # repository (hanserdesu/WCP-MultiLanguage) publishes one resource tag per
    # language (wcp-<lang>-resources-*), and hanserdesu/japanese keeps its own
    # tags (wcp-jp-*).  Mapping tag -> id lets one repo carry many wordbooks
    # and keeps discovery working after legacy per-language repositories are
    # removed (2026-09-15 cleanup).
    $repos = Get-GitHubJson ("https://api.github.com/users/{0}/repos?per_page=100&sort=updated" -f $owner)
    $repoRows = @($repos | Where-Object {
        [string](Get-FieldOr $_ 'full_name' '') -match ('^' + [regex]::Escape($owner) + '/(?:japanese|WCP-MultiLanguage)$')
    })
    $byId = @{}
    foreach ($wb in @($base.wordbooks)) { $byId[[string]$wb.id] = $wb }
    # Resource releases are tagged per language: wcp-<lang>-resources-*.  The
    # japanese repository keeps its legacy wcp-jp-* tag naming, mapped to the
    # catalog id 'ja'.  Grouping all releases of a repository by tag language
    # lets one repo carry many wordbooks and never mixes another language's
    # assets into a row (a repo-wide /releases/latest would).
    $langTagPattern = [regex]::new('^wcp-([a-z0-9]+)-resources-', 'IgnoreCase')
    foreach ($repo in $repoRows) {
        $repoName = [string](Get-FieldOr $repo 'full_name' '')
        try {
            $releases = Get-GitHubJson ("https://api.github.com/repos/{0}/releases?per_page=100" -f $repoName)
            $byLang = @{}
            foreach ($release in @($releases)) {
                $m = $langTagPattern.Match([string](Get-FieldOr $release 'tag_name' ''))
                if (-not $m.Success) { continue }
                $langId = $m.Groups[1].Value.ToLowerInvariant()
                if ($langId -eq 'jp') { $langId = 'ja' }
                if (-not $byLang.ContainsKey($langId)) {
                    $byLang[$langId] = New-Object System.Collections.Generic.List[object]
                }
                [void]$byLang[$langId].Add($release)
            }
            foreach ($langId in @($byLang.Keys)) {
                $seed = $byId[$langId]
                if (-not $seed) {
                    $seed = [pscustomobject]@{
                        id = $langId; status = 'pending_release'; language = $langId
                        display_name = $langId + ' 词书'; repo = $repoName; release_tag = ''
                        version = ''; word_count = 0; fingerprint_sha256 = ''; es3_prefix = $langId
                        disk = [pscustomobject]@{ extract_mb = 0 }; assets = @()
                    }
                }
                # Keep the candidate with the richest verified asset set, so a
                # small core/mod release never hides a newer resource release.
                $best = $null
                $bestAssetCount = -1
                foreach ($candidate in @($byLang[$langId])) {
                    $remote = New-RemoteWordbook $seed $candidate $repoName
                    if (-not $remote) { continue }
                    $assetCount = @($remote.assets).Count
                    if ($assetCount -gt $bestAssetCount -or
                        ($assetCount -eq $bestAssetCount -and $best -eq $null)) {
                        $best = $remote
                        $bestAssetCount = $assetCount
                    }
                }
                if ($best) { $byId[$langId] = $best }
            }
        } catch {
            Write-Verbose ("GitHub 词书发现跳过 {0}: {1}" -f $repoName, $_.Exception.Message)
        }
    }
    $rows = @($byId.Values | Sort-Object id)
    $result = [pscustomobject]@{ schema = 1; updated = (Get-Date).ToString('yyyy-MM-dd'); wordbooks = $rows }
    Assert-WordbookCatalog -Catalog $result
    return $result
}

$catalog = Import-WordbookCatalog -Path $catalogPathResolved
$cachePath = Join-Path $data 'hub-catalog-cache.json'
if (-not $Offline) {
    try {
        if (-not (Test-Path -LiteralPath $data)) { New-Item -ItemType Directory -Path $data -Force | Out-Null }
        $mergedCatalog = Get-GitHubCatalog -base $catalog -owner $GitHubOwner
        # Get-GitHubCatalog 只重建词书行；mods 块（mod 本体资产）必须原样带过，
        # 否则在线刷新一次后 mod 载荷元数据就丢了。
        if ((Get-PropertyNames $catalog) -contains 'mods') {
            $mergedCatalog | Add-Member -NotePropertyName mods -NotePropertyValue $catalog.mods -Force
        }
        $catalog = $mergedCatalog
        $catalog | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $cachePath -Encoding UTF8
        Write-Verbose '已从 GitHub 刷新词书目录'
    } catch {
        Write-Warning ('GitHub 目录刷新失败，使用随包目录: ' + $_.Exception.Message)
        if (Test-Path -LiteralPath $cachePath) {
            try {
                $cached = Import-WordbookCatalog -Path $cachePath
                # 缓存只在比随包目录更新时才顶替它：旧缓存可能钉住已经下线的 release 或
                # 尚未发布的 draft tag（2026-09-15 实测：旧缓存把 fr/ja 指向 404 的资源）。
                $cacheDate = [datetime]::MinValue
                $packDate = [datetime]::MinValue
                [void][datetime]::TryParse([string](Get-FieldOr $cached 'updated' ''), [ref]$cacheDate)
                [void][datetime]::TryParse([string](Get-FieldOr $catalog 'updated' ''), [ref]$packDate)
                if ($cacheDate -gt $packDate) { $catalog = $cached }
                else { Write-Verbose '缓存目录不比随包目录新，继续使用随包目录' }
            } catch { Write-Warning '缓存目录无效，继续使用随包目录' }
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
    # Windows PowerShell 5.1 (.NET Framework) 的 ExtractToDirectory 没有 bool
    # overwrite 重载（第三个参数是 Encoding，传 $true 会抛 InvalidCastException
    # —— 2026-09-15 沙箱实测，这就是在线安装此前从未成功过的原因）。逐条目
    # ExtractToFile(..., $true) 提供同样的覆盖语义。
    $zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        foreach ($entry in $zip.Entries) {
            if ($entry.FullName -match '(^|[\\/])\.\.([\\/]|$)') {
                throw ('zip 条目越界，已拒绝: ' + $entry.FullName)
            }
            if ($entry.Name -eq '') { continue }  # 目录条目
            $targetPath = Join-Path $dest ($entry.FullName -replace '/', '\')
            $targetDir = Split-Path -Parent $targetPath
            if ($targetDir -and -not (Test-Path -LiteralPath $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $targetPath, $true)
        }
    } finally { $zip.Dispose() }
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

# ---------- 通用下载（供自更新使用；与主安装循环同一套代理/超时约定） ----------
function Invoke-HubDownload([string]$uri, [string]$destination, [int]$timeoutMs = 120000) {
    $request = [Net.HttpWebRequest]::Create($uri)
    $request.Method = 'GET'
    $request.Timeout = $timeoutMs
    $request.ReadWriteTimeout = $timeoutMs
    $request.Proxy = [Net.WebRequest]::DefaultWebProxy
    if ($request.Proxy) { $request.Proxy.Credentials = [Net.CredentialCache]::DefaultCredentials }
    $response = $request.GetResponse()
    try {
        $stream = $response.GetResponseStream()
        $fs = [IO.File]::Create($destination)
        try {
            $buf = New-Object byte[] 262144
            while (($n = $stream.Read($buf, 0, $buf.Length)) -gt 0) { $fs.Write($buf, 0, $n) }
        } finally { $fs.Dispose() }
        $stream.Dispose()
    } finally { $response.Dispose() }
}

# ---------- 安装器自更新（学习 ja 方案 C：有新版才提示，用户确认才切换，失败不阻断） ----------
# 版本号由 run-installer.ps1 通过环境变量注入；直接运行脚本的老用户没有版本号，
# 自更新检查整体跳过（纯增益路径，不改变任何既有行为）。
$selfVersion = if ($env:WCP_INSTALLER_VERSION) { $env:WCP_INSTALLER_VERSION } else { '' }
if ($selfVersion -and -not $Offline -and -not $Plan -and -not $List) {
    try {
        # 版本索引（release-index.json）发布在 mods release（wcp-mods-v*）上，
        # 与安装器解耦：发新版只需替换该资产，老安装器即可发现新核心包。
        $modsRel = $null
        try {
            $modsRel = Get-GitHubJson 'https://api.github.com/repos/hanserdesu/WCP-MultiLanguage/releases?per_page=100' |
                Where-Object { ([string](Get-FieldOr $_ 'tag_name' '')) -like 'wcp-mods-*' } |
                Sort-Object -Property created_at -Descending | Select-Object -First 1
        } catch { }
        $idxAsset = if ($modsRel) { @($modsRel.assets | Where-Object { $_.name -eq 'release-index.json' })[0] } else { $null }
        $indexObj = $null
        if ($idxAsset) {
            $idxTmp = Join-Path $data 'release-index.json.check'
            try {
                Invoke-HubDownload $idxAsset.url $idxTmp
                $indexObj = Get-Content -LiteralPath $idxTmp -Raw -Encoding UTF8 | ConvertFrom-Json
                Remove-Item -LiteralPath $idxTmp -Force -ErrorAction SilentlyContinue
            } catch {
                Write-Host '自更新检查：在线获取版本信息失败（不影响本次安装）。' -ForegroundColor DarkGray
                if (Test-Path -LiteralPath $idxTmp) { Remove-Item -LiteralPath $idxTmp -Force -ErrorAction SilentlyContinue }
            }
        }
        if ($indexObj -and (Get-FieldOr $indexObj 'installer_version' '') -and
            [string]$indexObj.installer_version -ne [string]$selfVersion) {
            Write-Host ''
            Write-Host "检测到安装器新版本 $($indexObj.installer_version)（当前 $selfVersion）。" -ForegroundColor Cyan
            Write-Host '新版本可能已修复你遇到的问题。是否下载并切换到新版后重新安装？' -ForegroundColor Cyan
            $answer = Read-Host '输入 y 确认更新，其他键跳过（默认跳过）'
            if ($answer -match '^[Yy]') {
                $core = $indexObj.core_installer
                $coreTmp = Join-Path (Get-HubWorkPath 'dl') ('installer_update_' + [guid]::NewGuid().ToString('N') + '.zip')
                try {
                    Invoke-HubDownload $core.url $coreTmp
                    $actualCoreSha = Get-Sha256Hex $coreTmp
                    if ($actualCoreSha -ne ([string]$core.sha256).ToLowerInvariant()) {
                        throw ('SHA-256 校验失败（实际 ' + $actualCoreSha + '）')
                    }
                    # 解到全新临时目录、校验通过后再切换；任何一步失败都留在当前版本继续装（fail-safe）。
                    $newPkgDir = Join-Path (Get-HubWorkPath 'dl') ('installer_update_' + [guid]::NewGuid().ToString('N'))
                    Expand-HubZip $coreTmp $newPkgDir
                    $newScript = Get-ChildItem -LiteralPath $newPkgDir -Recurse -Filter 'Install-WCP-Wordbooks.ps1' |
                        Select-Object -First 1
                    if (-not $newScript) { throw '新包缺少 Install-WCP-Wordbooks.ps1' }
                    Remove-Item -LiteralPath $coreTmp -Force -ErrorAction SilentlyContinue
                    Write-Host "即将切换到新版安装器 $($indexObj.installer_version) 并重新开始安装。" -ForegroundColor Green
                    Write-Host '本窗口可以关闭；新版窗口会自动打开。' -ForegroundColor Green
                    Start-Process -FilePath 'powershell.exe' `
                        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $newScript.FullName) `
                        -WorkingDirectory (Split-Path -Parent $newScript.FullName)
                    exit 0
                } catch {
                    Write-Host ('新版安装器准备失败：' + $_.Exception.Message) -ForegroundColor Yellow
                    Write-Host '将继续使用当前版本完成安装。' -ForegroundColor Yellow
                    if (Test-Path -LiteralPath $coreTmp) { Remove-Item -LiteralPath $coreTmp -Force -ErrorAction SilentlyContinue }
                }
            }
        } elseif ($indexObj -and (Get-FieldOr $indexObj 'installer_version' '')) {
            Write-Host ('安装器已是最新版本（' + $selfVersion + '）。') -ForegroundColor DarkGray
        }
    } catch {
        # 自更新检查是纯增益路径：任何异常都不能阻断安装。
        Write-Host '自更新检查异常（不影响本次安装）。' -ForegroundColor DarkGray
    }
}

# ---------- 工作目录卫生（学习 ja 实战经验，全部失败不阻断） ----------
# 下载临时文件（hub_dl_*，zip 可达数百 MB）与解压残留绝不能留在
# LocalLow\WCP\wcp 内：Steam 对该游戏的云同步范围是整个 wcp 目录，
# 这些没有同步价值的大文件会撑爆云同步配额，导致 MyBook.es3 等关键
# 存档永远排不进同步队列（ja 2026-09-16 实测 53 万文件/约 15GB 长期
# 「无法同步」）。工作目录与 packs 同级，不在云同步范围内。
$hubWorkRoot = Join-Path $wcpRoot 'wcp_hub_work'
New-Item -ItemType Directory -Force -Path $hubWorkRoot | Out-Null

function Get-HubWorkPath([string]$kind) {
    # kind: 'dl'（下载临时）| 'backup'（旧包备份）。返回该类工作路径；
    # 历史遗留的 wcp 内旧位置由 Move-LegacyHubWork 搬出。
    if ($kind -eq 'dl') { return (Join-Path $hubWorkRoot 'downloads') }
    if ($kind -eq 'backup') { return (Join-Path $hubWorkRoot 'backups') }
    return $hubWorkRoot
}

function Move-LegacyHubWork {
    # 旧版本安装器把 hub_dl_* 和备份直接写进 wcp（云同步范围）。一次性
    # 搬到新工作根：同盘 Move 是瞬间重命名；目标已存在的项跳过；任何
    # 失败只提示（旧文件留在原地只是多占点磁盘，不影响安装）。
    foreach ($pair in @(@('hub_dl_*', 'downloads'), @('hub_backup_*', 'backups'))) {
        $legacy = @(Get-ChildItem -LiteralPath $data -Filter $pair[0] -Force -ErrorAction SilentlyContinue)
        if ($legacy.Count -eq 0) { continue }
        $targetDir = Get-HubWorkPath $pair[1]
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        $moved = 0
        foreach ($item in $legacy) {
            $target = Join-Path $targetDir $item.Name
            if (Test-Path -LiteralPath $target) { continue }
            try {
                Move-Item -LiteralPath $item.FullName -Destination $target -Force -ErrorAction Stop
                $moved++
            } catch { }
        }
        if ($moved -gt 0) {
            Write-Host ("已把 {0} 项移出 Steam 云同步范围：{1}" -f $moved, $targetDir) -ForegroundColor DarkGray
        }
    }
}

function Remove-HubStaleWork {
    # 清理上次安装的残留下载临时目录/文件（正常流程结束时已自删，这里兜底
    # 处理中断留下的），并只保留最近 3 份旧包备份。所有删除都允许失败。
    $freed = [int64]0
    $dlDir = Get-HubWorkPath 'dl'
    if (Test-Path -LiteralPath $dlDir) {
        foreach ($f in @(Get-ChildItem -LiteralPath $dlDir -Recurse -Force -ErrorAction SilentlyContinue)) {
            $size = if (-not $f.PSIsContainer) { $f.Length } else { 0 }
            try { Remove-Item -LiteralPath $f.FullName -Recurse -Force -ErrorAction Stop; $freed += $size } catch { }
        }
    }
    $backupDir = Get-HubWorkPath 'backup'
    if (Test-Path -LiteralPath $backupDir) {
        $stale = @(Get-ChildItem -LiteralPath $backupDir -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending | Select-Object -Skip 3)
        foreach ($s in $stale) {
            $size = 0
            try {
                $size = [int64]((Get-ChildItem -LiteralPath $s.FullName -Recurse -File -ErrorAction SilentlyContinue |
                    Measure-Object Length -Sum).Sum)
            } catch { }
            try { Remove-Item -LiteralPath $s.FullName -Recurse -Force -ErrorAction Stop; $freed += $size } catch { }
        }
    }
    if ($freed -gt 1MB) {
        Write-Host ("已清理安装工作残留，释放约 {0:N0} MB。" -f ($freed / 1MB)) -ForegroundColor DarkGray
    }
}

function Backup-HubPack([string]$packDir, [string]$backupRoot, [string]$langId) {
    # 覆盖前备份旧语言包，跳过 audio 子树：音频体积大（每语 1~2 GB）且每次
    # 更新都全量重新下载，旧音频备份毫无回滚价值，只会把备份目录撑爆。
    # 失败只提示，绝不阻断本次安装（备份只是回滚保险，不是必经路径）。
    if (-not (Test-Path -LiteralPath $packDir)) { return }
    try {
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $target = Join-Path $backupRoot ("{0}_{1}" -f $stamp, $langId)
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        foreach ($item in @([IO.Directory]::EnumerateFileSystemEntries($packDir))) {
            $name = [IO.Path]::GetFileName($item)
            if ($name -ieq 'audio') { continue }
            $dst = Join-Path $target $name
            if ([IO.Directory]::Exists($item)) {
                [IO.Directory]::CreateDirectory($dst) | Out-Null
                foreach ($f in [IO.Directory]::EnumerateFiles($item, '*', [IO.SearchOption]::AllDirectories)) {
                    $rel = $f.Substring($item.Length).TrimStart('\', '/')
                    $dstF = Join-Path $dst $rel
                    $dstParent = Split-Path -Parent $dstF
                    if (-not [string]::IsNullOrEmpty($dstParent)) { [IO.Directory]::CreateDirectory($dstParent) | Out-Null }
                    [IO.File]::Copy($f, $dstF, $true)
                }
            } else {
                [IO.File]::Copy($item, $dst, $true)
            }
        }
        Write-Host ('  已备份旧包（不含音频）→ ' + $target) -ForegroundColor DarkGray
    } catch {
        Write-Host ('  旧包备份失败（不影响本次安装）：' + $_.Exception.Message) -ForegroundColor DarkYellow
    }
}

Move-LegacyHubWork
Remove-HubStaleWork

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

# Mod 本体（BepInEx 插件）与词书资源分开管理：catalog 顶层的 mods 块描述全局
# mod 载荷，与选择了哪本词书无关。安装/更新任何词书之前先保证 mod 已就位，这样
# "装完 mod 后槽位扩到 20 条" 对任何语言都成立。state.mods.files 按 sha256 记账，
# 与词书行同规则：只有通过下载+校验+展开的资产才写进状态，失败资产留在状态外，
# 下次 -Update 自动重试。
function Install-HubMods([string]$gameRoot, $Catalog, $HubState) {
    if ((Get-PropertyNames $Catalog) -notcontains 'mods') { return $null }
    $mods = $Catalog.mods
    $mn = Get-PropertyNames $mods
    foreach ($f in @('version', 'assets')) {
        if ($mn -notcontains $f) { throw 'catalog.mods 缺少字段: ' + $f }
    }
    # 载荷 zip 的条目路径是 BepInEx 相对布局（plugins/WcpHost.dll，与日语一键包
    # payload 约定一致），所以解到 BepInEx 根，而不是 plugins 目录里再套一层。
    $modsRoot = Join-Path $gameRoot 'BepInEx'
    $stateEntry = $null
    if ($HubState -and (Get-PropertyNames $HubState) -contains 'mods') { $stateEntry = $HubState.mods }
    $oldFiles = if ($stateEntry -and $stateEntry.files) { $stateEntry.files } else { $null }
    $versionChanged = -not $stateEntry -or [string]$stateEntry.version -ne [string]$mods.version
    $pending = New-Object System.Collections.Generic.List[object]
    foreach ($a in @($mods.assets)) {
        $known = $false
        if ($oldFiles -and (Get-PropertyNames $oldFiles) -contains [string]$a.name) {
            $known = ([string]$oldFiles.($a.name).sha256 -eq [string]$a.sha256)
        }
        if ($versionChanged -or -not $known) { [void]$pending.Add($a) }
    }
    $entry = [pscustomobject]@{ version = [string]$mods.version; files = $null }
    if ($pending.Count -eq 0) {
        Write-Host ('  mod: 已是最新（{0}）' -f $mods.version)
        $entry.files = $oldFiles
        return $entry
    }
    if (-not (Test-Path -LiteralPath $modsRoot)) {
        New-Item -ItemType Directory -Path $modsRoot -Force | Out-Null
    }
    $files = [pscustomobject]@{}
    foreach ($a in $pending) {
        Write-Host ('  mod: {0} ({1} MB)' -f $a.name, [math]::Round($a.size / 1MB, 1))
        $tmp = Join-Path (Get-HubWorkPath 'dl') ('hub_dl_' + [guid]::NewGuid().ToString('N'))
        try {
            $request = [Net.HttpWebRequest]::Create($a.url)
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
            if ($actual -ne ([string]$a.sha256).ToLowerInvariant()) {
                throw ('SHA-256 不匹配: ' + $a.name + ' 期望 ' + $a.sha256 + ' 实际 ' + $actual)
            }
            if ([string]$a.name -match '(?i)\.(zip|7z|tar|gz)$') {
                Expand-HubZip $tmp $modsRoot
            } else {
                Copy-Item -LiteralPath $tmp -Destination (Join-Path $modsRoot $a.name) -Force
            }
            Remove-Item -LiteralPath $tmp -Force
            $files | Add-Member -NotePropertyName $a.name -NotePropertyValue ([pscustomobject]@{ sha256 = $a.sha256; size = $a.size })
        } catch {
            $errors.Add('mod/' + $a.name + ': ' + $_.Exception.Message)
            if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
            continue
        }
    }
    if (@($files.PSObject.Properties).Count -gt 0) { $entry.files = $files }
    elseif ($oldFiles) { $entry.files = $oldFiles }
    return $entry
}

$totalAssets = 0
foreach ($wb in $selection) {
    $changedForCount = @(Get-WordbookAssetDiff -Wordbook $wb -InstalledState $installed)
    if ($Update) { $totalAssets += $changedForCount.Count }
    elseif (-not (Test-WordbookInstalledFully -Wordbook $wb -InstalledState $installed)) { $totalAssets += @($wb.assets).Count }
}
$done = 0
$errors = New-Object System.Collections.Generic.List[string]

# Mod 本体先行：catalog 带 mods 块时，先把 BepInEx 插件装到位再装词书资源。
$modsEntry = Install-HubMods -gameRoot $game -Catalog $catalog -HubState $state
if ($modsEntry) {
    if ((Get-PropertyNames $state) -contains 'mods') { $state.mods = $modsEntry }
    else { $state | Add-Member -NotePropertyName mods -NotePropertyValue $modsEntry }
    Save-HubState
}

foreach ($wb in $selection) {
    $ns = Join-Path $data ($wb.es3_prefix + '_hub_payload')
    $packRoot = Join-Path $packsRoot ([string]$wb.language)
    $changed = @(Get-WordbookAssetDiff -Wordbook $wb -InstalledState $installed)
    if ($changed.Count -eq 0 -and (Test-WordbookInstalledFully -Wordbook $wb -InstalledState $installed)) {
        Write-Host ('  {0}: 已是最新，跳过' -f $wb.id); continue
    }
    # 有内容要覆盖前先备份旧包（跳过 audio，见 Backup-HubPack；失败不阻断）。
    if ((Test-Path -LiteralPath $packRoot) -and $changed.Count -gt 0) {
        Backup-HubPack -packDir $packRoot -backupRoot (Get-HubWorkPath 'backup') -langId ([string]$wb.language)
    }
    if (-not (Test-Path -LiteralPath $ns)) { New-Item -ItemType Directory -Path $ns -Force | Out-Null }

    $files = if ($Update) { $changed } else { @($wb.assets) }
    $succeeded = @{}
    foreach ($asset in $files) {
        $done++
        Write-Host ('  [{0}/{1}] {2}: {3}' -f $done, $totalAssets, $wb.id, $asset.name)
        $tmp = Join-Path (Get-HubWorkPath 'dl') ('hub_dl_' + [guid]::NewGuid().ToString('N'))
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
                if ($asset.kind -eq 'word_audio') {
                    # 兼容层：游戏的 VocabularyAudioPlayer 只认 <LocalLow>\WCP\vocabulary
                    # （引擎自带路径）。宿主未接管时该目录为空会让发音静默回退成游戏
                    # 的英语 AI 语音，所以单词音频在 pack 之外再镜像一份。失败只提示。
                    $vocabMirror = Join-Path $wcpRoot 'vocabulary'
                    $mirrored = Sync-WordAudioMirror -SourceDir $dest -VocabDir $vocabMirror
                    if ($mirrored -lt 0) {
                        Write-Host ('    提示：单词音频镜像到游戏原生目录失败（不影响主安装）：{0}' -f $vocabMirror) -ForegroundColor DarkYellow
                    } else {
                        Write-Host ('    单词音频镜像到游戏原生目录：{0} 个 → {1}' -f $mirrored, $vocabMirror)
                    }
                }
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
