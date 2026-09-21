# Normalize line endings so an edit does not show up as a whole-file rewrite.
# -To CRLF or -To LF selects the target convention.
param(
  [Parameter(Mandatory = $true)][string[]]$Path,
  [Parameter(Mandatory = $true)][ValidateSet('LF','CRLF')][string]$To
)
$ErrorActionPreference = 'Stop'
$enc = New-Object System.Text.UTF8Encoding($false)
$CRLF = [string][char]13 + [string][char]10
$LF = [string][char]10
foreach ($p in $Path) {
  $s = [System.IO.File]::ReadAllText($p)
  if ($To -eq 'LF') {
    $out = $s.Replace($CRLF, $LF)
  } else {
    # Only convert bare LF; keep existing CRLF pairs intact.
    $out = [regex]::Replace($s, '(?<![\r])' + [regex]::Escape($LF), $CRLF)
  }
  [System.IO.File]::WriteAllText($p, $out, $enc)
  $x = [System.IO.File]::ReadAllText($p)
  $crlf = ([regex]::Matches($x, [regex]::Escape($CRLF))).Count
  $lf = ([regex]::Matches($x, '(?<![\r])' + [regex]::Escape($LF))).Count
  Write-Host ("{0,-56} CRLF={1} bareLF={2}" -f $p, $crlf, $lf)
}
