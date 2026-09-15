param([string]$Path, [string]$Text)
$b = [System.IO.File]::ReadAllBytes($Path)
function Find-Bytes([byte[]]$hay, [byte[]]$pat) {
  for ($i = 0; $i -le $hay.Length - $pat.Length; $i++) {
    $ok = $true
    for ($j = 0; $j -lt $pat.Length; $j++) {
      if ($hay[$i + $j] -ne $pat[$j]) { $ok = $false; break }
    }
    if ($ok) { return $true }
  }
  return $false
}
$enc = [System.Text.Encoding]::UTF8
foreach ($name in @('UTF8','UTF16LE','GBK')) {
  switch ($name) {
    'UTF8'    { $p = $enc.GetBytes($Text) }
    'UTF16LE' { $p = [System.Text.Encoding]::Unicode.GetBytes($Text) }
    'GBK'     { $p = [System.Text.Encoding]::GetEncoding(936).GetBytes($Text) }
  }
  Write-Output ($name + ' : ' + (Find-Bytes $b $p))
}
