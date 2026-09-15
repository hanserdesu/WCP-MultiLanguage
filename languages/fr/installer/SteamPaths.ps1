function Add-Candidate([System.Collections.Generic.List[string]]$list, [string]$path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return }
    try { $full = [IO.Path]::GetFullPath($path).TrimEnd('\') } catch { return }
    if (-not $list.Contains($full)) { $list.Add($full) }
}

function Get-SteamRoots {
    $roots = New-Object 'System.Collections.Generic.List[string]'
    foreach ($hive in @('HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKLM:\SOFTWARE\Valve\Steam')) {
        try {
            $item = Get-ItemProperty -Path $hive -ErrorAction Stop
            Add-Candidate $roots ([string]$item.SteamPath)
            Add-Candidate $roots ([string]$item.InstallPath)
        } catch {}
    }
    $initial = @($roots)
    foreach ($root in $initial) {
        if (-not [IO.Directory]::Exists($root)) {
            Write-Host "跳过不存在的 Steam 路径：$root" -ForegroundColor DarkYellow
            continue
        }
        $vdf = Join-Path $root 'steamapps\libraryfolders.vdf'
        if (-not (Test-Path -LiteralPath $vdf)) { continue }
        try {
            $raw = Get-Content -LiteralPath $vdf -Raw -ErrorAction Stop
            foreach ($m in [regex]::Matches($raw, '"path"\s*"([^"]+)"')) {
                Add-Candidate $roots ($m.Groups[1].Value -replace '\\\\','\')
            }
        } catch {}
    }
    return @($roots | Where-Object { [IO.Directory]::Exists($_) })
}

function Get-GameCandidates {
    $list = New-Object 'System.Collections.Generic.List[string]'
    Add-Candidate $list $env:WCP_GAME_DIR
    foreach ($root in (Get-SteamRoots)) {
        if (-not [IO.Directory]::Exists($root)) { continue }
        Add-Candidate $list (Join-Path $root 'steamapps\common\WCP-WordGirlgriend')
    }
    foreach ($root in @('C:\Program Files (x86)\Steam\steamapps\common', 'C:\Program Files\Steam\steamapps\common')) {
        Add-Candidate $list (Join-Path $root 'WCP-WordGirlgriend')
    }
    $valid = New-Object 'System.Collections.Generic.List[string]'
    foreach ($candidate in @($list)) {
        if (-not [IO.Directory]::Exists($candidate)) {
            if ($candidate -match '^[A-Za-z]:') {
                Write-Host "跳过不存在的游戏路径：$candidate" -ForegroundColor DarkYellow
            }
            continue
        }
        $managed = Join-Path $candidate 'wcp_Data\Managed\Assembly-CSharp.dll'
        $database = Join-Path $candidate 'wcp_Data\StreamingAssets\wcpFullEng.db'
        if ((Test-Path -LiteralPath $managed) -and (Test-Path -LiteralPath $database)) {
            $valid.Add($candidate)
        }
    }
    return @($valid)
}

