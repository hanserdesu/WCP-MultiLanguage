# Deploy the freshly built JpWordListMod.dll as soon as the running game exits.
$ErrorActionPreference = "Continue"
$src = "D:\Japanese\mod_jp_wordlist\JpWordListMod.dll"
$dst = "E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\JpWordListMod.dll"
$log = "D:\Japanese\work\tmp\deploy_jpwordlist.log"
$deadline = (Get-Date).AddMinutes(60)

function Write-Log([string]$m) {
  Add-Content -LiteralPath $log -Value (("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m)) -Encoding utf8
}

Set-Content -LiteralPath $log -Value (("{0} waiting for the game (wcp) to exit" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))) -Encoding utf8
while ((Get-Date) -lt $deadline) {
  if (-not (Get-Process -Name wcp -ErrorAction SilentlyContinue)) { break }
  Start-Sleep -Seconds 5
}
if (Get-Process -Name wcp -ErrorAction SilentlyContinue) {
  Write-Log "TIMEOUT: game still running, nothing deployed"
  exit 1
}
Start-Sleep -Seconds 4
for ($i = 1; $i -le 12; $i++) {
  try {
    Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop
    # Get-FileHash 在这台机器上取不到(隐藏窗口里的 ps 解析不到该 cmdlet), 用 .NET 直接算
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $h = [System.BitConverter]::ToString($sha.ComputeHash([System.IO.File]::ReadAllBytes($dst)))
    $hs = [System.BitConverter]::ToString($sha.ComputeHash([System.IO.File]::ReadAllBytes($src)))
    if ($h -eq $hs) { Write-Log ("DEPLOYED ok sha256=" + $h); exit 0 }
    Write-Log ("MISMATCH after copy: dst=" + $h + " src=" + $hs)
  } catch {
    Write-Log ("copy attempt " + $i + " failed: " + $_.Exception.Message)
  }
  Start-Sleep -Seconds 5
}
Write-Log "FAILED: could not replace the plugin dll"
exit 1
