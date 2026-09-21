@echo off
rem Build + run probes/es3bench/probe1.cs -- real-ES3 offline A/B (sequential vs batch).
rem Usage: run_probe1.cmd <src.es3> <workdir>
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set CSC=%FW%\csc.exe
set HERE=%~dp0
"%CSC%" /nologo /noconfig /target:exe /langversion:5 /codepage:65001 ^
  /r:"%FW%\System.dll" /r:"%FW%\System.Core.dll" ^
  /out:"%HERE%probe1.exe" "%HERE%probe1.cs" > "%HERE%probe1_build.txt" 2>&1
if errorlevel 1 (echo CSC FAILED & type "%HERE%probe1_build.txt" & exit /b 1)
"%HERE%probe1.exe" "%HERE%probe1_out.txt" "%~1" "%~2"
type "%HERE%probe1_out.txt"
endlocal
