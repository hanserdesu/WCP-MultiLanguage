$ErrorActionPreference = 'Stop'
$outputDir = Join-Path $env:TEMP ('wcp-wordaudio-compat-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $outputDir | Out-Null
$exe = Join-Path $outputDir 'WordAudioCompatTest.exe'
& "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:exe /langversion:5 /codepage:65001 "/out:$exe" "$PSScriptRoot\WordAudioCompatTest.cs" "$PSScriptRoot\..\WordAudioCompat.cs"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $exe
exit $LASTEXITCODE
