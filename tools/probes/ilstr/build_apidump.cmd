@echo off
rem Build probes/ilstr/apidump.cs (Mono.Cecil API surface dumper).
rem Desktop .NET Framework only -- /nostdlib+ against the game's mscorlib produces
rem an assembly whose generic type refs fail to load at runtime (TypeLoadException
rem on Stack`1). Mirror build_ilscan.cmd instead. Pure ASCII on purpose.
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set CSC=%FW%\csc.exe
set HERE=%~dp0
"%CSC%" /nologo /noconfig /target:exe /langversion:5 /codepage:65001 /r:"%FW%\System.dll" /r:"%FW%\System.Core.dll" /r:"%GAME%\BepInEx\core\Mono.Cecil.dll" /out:"%HERE%apidump.exe" "%HERE%apidump.cs" > "%HERE%apidump_build.txt" 2>&1
echo EXITCODE=%ERRORLEVEL%
type "%HERE%apidump_build.txt"
endlocal
