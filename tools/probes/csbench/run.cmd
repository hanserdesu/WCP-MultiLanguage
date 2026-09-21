@echo off
rem Build + run the offline cost benchmark. csc.exe is sandbox-blocked when invoked
rem directly, so this .cmd wrapper is the sanctioned path (see project memory).
setlocal
set HERE=%~dp0
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
"%CSC%" /nologo /target:exe /platform:x64 /optimize+ /out:"%HERE%Bench.exe" "%HERE%Bench.cs" > "%HERE%csc.out.txt" 2>&1
if errorlevel 1 (echo CSC FAILED & exit /b 1)
rem PowerShell tool swallows stdout -> always land the result in a file.
"%HERE%Bench.exe" > "%HERE%run.out.txt" 2>&1
type "%HERE%run.out.txt"
endlocal
