$tokens = $null
$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$tokens, [ref]$errors)
if ($errors -and $errors.Count) {
    $errors | ForEach-Object { Write-Output ("{0}: {1}" -f $_.Extent.StartLineNumber, $_.Message) }
    exit 1
}
Write-Output 'PARSE OK'
