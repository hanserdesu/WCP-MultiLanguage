$ErrorActionPreference = 'Continue'
$mgd = 'E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\Managed'
[System.AppDomain]::CurrentDomain.add_ReflectionOnlyAssemblyResolve({
  param($s, $e)
  $name = ($e.Name -split ',')[0]
  $p = Join-Path 'E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\Managed' ($name + '.dll')
  if (Test-Path $p) { return [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($p) }
  return [System.Reflection.Assembly]::ReflectionOnlyLoad($e.Name)
})
foreach ($n in @('Assembly-CSharp-firstpass.dll','Assembly-CSharp.dll')) {
  try {
    $a = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom((Join-Path $mgd $n))
    $t = $a.GetType('ES3')
    if ($t) {
      Write-Output ('FOUND ES3 in ' + $n)
      $t.GetMethods('Public,Static') | Where-Object { $_.Name -eq 'Load' -or $_.Name -eq 'Save' } |
        ForEach-Object {
          $ps = ($_.GetParameters() | ForEach-Object { $_.ParameterType.Name + ' ' + $_.Name }) -join ', '
          Write-Output ('  ' + $_.Name + '(' + $ps + ')')
        }
    }
  } catch { Write-Output ('ERR ' + $n + ': ' + $_.Exception.Message) }
}
