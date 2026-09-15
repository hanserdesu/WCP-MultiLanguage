$ErrorActionPreference = 'Stop'
$outputDir = Join-Path $env:TEMP ('wcp-takeover-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $outputDir | Out-Null
$exe = Join-Path $outputDir 'TakeoverScopeTest.exe'
& "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:exe /langversion:5 /codepage:65001 "/out:$exe" "$PSScriptRoot\TakeoverScopeTest.cs" "$PSScriptRoot\..\TakeoverScope.cs" "$PSScriptRoot\..\Core\BookPool.cs"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $exe
exit $LASTEXITCODE
