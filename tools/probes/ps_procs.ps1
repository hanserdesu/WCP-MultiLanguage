Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|dotnet|WCP|WordGirl' } | ForEach-Object {
  $cmd = $_.CommandLine
  if ($null -eq $cmd) { $cmd = '(n/a)' }
  if ($cmd.Length -gt 200) { $cmd = $cmd.Substring(0,200) }
  "{0}|{1}|{2}" -f $_.ProcessId, $_.Name, $cmd
}
