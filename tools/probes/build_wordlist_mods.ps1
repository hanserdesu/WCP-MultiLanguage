# Compile the five per-language wordlist plugins to a scratch dir.
# Read-only with respect to the game: never writes into BepInEx\plugins.
param(
  [string]$OutDir = "$env:TEMP\atl-build-probe"
)
$ErrorActionPreference = 'Stop'
$game = 'E:\Steam\steamapps\common\WCP-WordGirlgriend'
$mgd = Join-Path $game 'wcp_Data\Managed'
$core = Join-Path $game 'BepInEx\core'
$csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

$refs = @(
  (Join-Path $core 'BepInEx.dll'), (Join-Path $core '0Harmony.dll'),
  (Join-Path $mgd 'Assembly-CSharp.dll'), (Join-Path $mgd 'Assembly-CSharp-firstpass.dll'),
  (Join-Path $mgd 'netstandard.dll'), (Join-Path $mgd 'mscorlib.dll'),
  (Join-Path $mgd 'System.dll'), (Join-Path $mgd 'System.Core.dll'),
  (Join-Path $mgd 'System.Data.dll'), (Join-Path $mgd 'Mono.Data.Sqlite.dll'),
  (Join-Path $mgd 'UnityEngine.dll'), (Join-Path $mgd 'UnityEngine.CoreModule.dll'),
  (Join-Path $mgd 'UnityEngine.UIModule.dll'), (Join-Path $mgd 'UnityEngine.AudioModule.dll'),
  (Join-Path $mgd 'UnityEngine.UnityWebRequestModule.dll'),
  (Join-Path $mgd 'UnityEngine.UnityWebRequestAudioModule.dll'),
  (Join-Path $mgd 'UnityEngine.UI.dll'),
  (Join-Path $mgd 'UnityEngine.TextRenderingModule.dll'),
  (Join-Path $mgd 'Unity.TextMeshPro.dll')
)
$refArgs = $refs | ForEach-Object { "/r:$_" }

$mods = @(
  @{ Name = 'FrWordListMod';  Dll = 'FrWordListMod.dll';  Src = 'French\mod_fr_wordlist' },
  @{ Name = 'DeWordListMod';  Dll = 'DeWordListMod.dll';  Src = 'German\mod_de_wordlist' },
  @{ Name = 'RuWordListMod';  Dll = 'RuWordListMod.dll';  Src = 'Russian\mod_ru_wordlist' },
  @{ Name = 'YueWordListMod'; Dll = 'YueWordListMod.dll'; Src = 'Contonese\mod_yue_wordlist' },
  @{ Name = 'JpWordListMod';  Dll = 'JpWordListMod.dll';  Src = 'Japanese\mod_jp_wordlist' }
)

foreach ($m in $mods) {
  $src = Join-Path $PSScriptRoot ('..\' + $m.Src)
  $cs = @(Get-ChildItem $src -Filter *.cs | ForEach-Object { $_.FullName })
  # Japanese keeps a single shared BookProfiles copy, referenced from
  # mod_jp_wordlist/build.cmd instead of living in the mod directory.
  if (-not (Test-Path (Join-Path $src 'BookProfiles.cs'))) {
    $shared = Join-Path $PSScriptRoot '..\Japanese\mod_book_name\BookProfiles.cs'
    if (Test-Path $shared) { $cs += (Resolve-Path $shared).Path }
  }
  $out = Join-Path $OutDir $m.Dll
  $args = @('/nologo','/noconfig','/nostdlib+','/target:library','/langversion:5',
            '/optimize+','/codepage:65001') + $refArgs + @("/out:$out") + $cs
  Write-Host ("=== " + $m.Name + " ===")
  $res = & $csc @args 2>&1
  if ($LASTEXITCODE -eq 0) { Write-Host ("BUILD OK  -> " + $out) }
  else {
    Write-Host ("BUILD FAILED (exit " + $LASTEXITCODE + ")")
    $res | Where-Object { $_ -match 'error' } | Select-Object -First 12 | ForEach-Object { Write-Host ("  " + $_) }
  }
}
