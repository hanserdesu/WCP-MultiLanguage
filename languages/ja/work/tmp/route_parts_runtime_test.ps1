$ErrorActionPreference = 'Stop'
$source = Get-Content -Raw 'wcp_wordbooks\installer\Install-WCP-Japanese.ps1'
$start = $source.IndexOf('function Get-Sha256')
$end = $source.IndexOf('function Ensure-ZipExtractor')
Invoke-Expression $source.Substring($start, $end - $start)
$start = $source.IndexOf('function Get-AssetUrl')
$end = $source.IndexOf('$wordAsset =')
Invoke-Expression $source.Substring($start, $end - $start)

$manifest = Get-Content -Raw 'wcp_wordbooks\output\release\release-manifest.json' | ConvertFrom-Json
$asset = $manifest.assets[0]
$serverRoot = (Resolve-Path 'wcp_wordbooks\output\release\gitee-parts').Path
$port = 18766
$server = Start-Process -FilePath 'python' -ArgumentList @(
    '-m', 'http.server', $port, '--bind', '127.0.0.1') -WorkingDirectory $serverRoot -WindowStyle Hidden -PassThru
$data = Join-Path $env:TEMP ('wcp-parts-route-test-' + [guid]::NewGuid().ToString('N'))
try {
    Start-Sleep -Milliseconds 700
    $script:data = $data
    $script:downloadRoutes = @([pscustomobject]@{
        Name = '本机模拟 Gitee 分卷'
        UrlTemplate = "http://127.0.0.1:$port/{name}"
        Mode = 'parts'
    })
    $target = Download-VerifiedAsset $asset
    if (-not (Test-Path -LiteralPath $target)) { throw 'target missing' }
    $hash = Get-Sha256 $target
    if ($hash -ne $asset.sha256) { throw "hash mismatch: $hash" }
    $leftover = @(Get-ChildItem -LiteralPath (Split-Path $target) -Filter ($asset.name + '.gitee.part*') -ErrorAction SilentlyContinue)
    if ($leftover.Count) { throw "part cache was not cleaned: $($leftover.Name -join ', ')" }
    Write-Output "PARTS ROUTE RUNTIME PASS: $($asset.name), parts=$(@($asset.parts).Count), size=$((Get-Item $target).Length), sha256=$hash"
} finally {
    if ($server) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $data) {
        Remove-Item -LiteralPath $data -Recurse -Force -ErrorAction SilentlyContinue
    }
}
