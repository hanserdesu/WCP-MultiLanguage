@echo off
rem Build + run probes/es3bench/probe0.cs -- can ES3 run outside Unity?
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set MGD=%GAME%\wcp_Data\Managed
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set CSC=%FW%\csc.exe
set HERE=%~dp0
"%CSC%" /nologo /noconfig /target:exe /langversion:5 /codepage:65001 ^
  /r:"%FW%\System.dll" /r:"%FW%\System.Core.dll" ^
  /out:"%HERE%probe0.exe" "%HERE%probe0.cs" > "%HERE%probe0_build.txt" 2>&1
if errorlevel 1 (echo CSC FAILED & type "%HERE%probe0_build.txt" & exit /b 1)
"%HERE%probe0.exe" "%HERE%probe0_out.txt"
type "%HERE%probe0_out.txt"
endlocal
