@echo off
rem Build + run the round-7 identity/UI-scan benchmark.
rem csc.exe is sandbox-blocked when invoked directly, so this .cmd wrapper is the
rem sanctioned path (see project memory). Output ALWAYS lands in a file because the
rem PowerShell/Bash tool may swallow stdout.
setlocal
set HERE=%~dp0
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
"%CSC%" /nologo /target:exe /platform:x64 /optimize+ /out:"%HERE%Bench2.exe" "%HERE%Bench2.cs" "%HERE%..\..\MultiLanguage\mod_host\Core\Json.cs" > "%HERE%csc2.out.txt" 2>&1
if errorlevel 1 (echo CSC FAILED & type "%HERE%csc2.out.txt" & exit /b 1)
"%HERE%Bench2.exe" > "%HERE%run2.out.txt" 2>&1
type "%HERE%run2.out.txt"
endlocal
