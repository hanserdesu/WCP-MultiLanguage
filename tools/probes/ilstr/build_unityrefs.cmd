@echo off
rem Build probes/ilstr/unityrefs.cs
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set CSC=%FW%\csc.exe
set HERE=%~dp0
"%CSC%" /nologo /noconfig /target:exe /langversion:5 /codepage:65001 /r:"%FW%\System.dll" /r:"%FW%\System.Core.dll" /r:"%GAME%\BepInEx\core\Mono.Cecil.dll" /out:"%HERE%unityrefs.exe" "%HERE%unityrefs.cs" > "%HERE%unityrefs_build.txt" 2>&1
echo EXITCODE=%ERRORLEVEL%
type "%HERE%unityrefs_build.txt"
endlocal
