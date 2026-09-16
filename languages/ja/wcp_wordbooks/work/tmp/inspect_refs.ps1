$cecil = "E:\steam\steamapps\common\WCP-WordGirlgriend\BepInEx\core\Mono.Cecil.dll"
Add-Type -Path $cecil
$files = @(
  "E:\steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\SentenceAudioFrMod.dll",
  "E:\steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\SentenceAudioDeMod.dll",
  "E:\steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\SentenceAudioRuMod.dll",
  "E:\steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\SentenceAudioYueMod.dll",
  "E:\steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\FrWordListMod.dll",
  "E:\steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\DeWordListMod.dll",
  "E:\steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\RuWordListMod.dll",
  "E:\steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\YueWordListMod.dll"
)
foreach ($f in $files) {
  $asm = [Mono.Cecil.AssemblyDefinition]::ReadAssembly($f)
  $refs = ($asm.MainModule.AssemblyReferences | ForEach-Object { $_.Name }) -join ', '
  $name = Split-Path $f -Leaf
  $bound = ($refs -split ', ') -contains 'Assembly-CSharp'
  Write-Host ("{0,-28} Assembly-CSharp={1}" -f $name, $bound)
  Write-Host ("    refs: $refs")
  $asm.Dispose()
}
