@echo off
rem Build + run probes/es3bench/probe2.cs -- real-ES3 offline A/B on a copy of the live save.
rem Usage: run_probe2.cmd <src.es3> <workdir> [nKeys]
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set MGD=%GAME%\wcp_Data\Managed
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set CSC=%FW%\csc.exe
set HERE=%~dp0
if not exist "%HERE%Mono.Cecil.dll" copy /y "%GAME%\BepInEx\core\Mono.Cecil.dll" "%HERE%Mono.Cecil.dll" > nul
"%CSC%" /nologo /noconfig /target:exe /langversion:5 /codepage:65001 ^
  /r:"%FW%\System.dll" /r:"%FW%\System.Core.dll" /r:"%GAME%\BepInEx\core\Mono.Cecil.dll" ^
  /out:"%HERE%probe2.exe" "%HERE%probe2.cs" > "%HERE%probe2_build.txt" 2>&1
if errorlevel 1 (echo CSC FAILED & type "%HERE%probe2_build.txt" & exit /b 1)
if "%~3"=="" (set NK=45) else (set NK=%~3)
"%HERE%probe2.exe" "%HERE%probe2_out.txt" "%~1" "%~2" "%MGD%" %NK%
type "%HERE%probe2_out.txt"
endlocal
