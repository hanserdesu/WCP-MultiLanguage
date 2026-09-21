@echo off
rem A/B: does the TakeoverScope offline harness compile against the PREVIOUS
rem (git HEAD) TakeoverScope.cs? If it fails there too, the harness was already
rem stale before this round's edits and the failure is not a regression.
setlocal
set HERE=%~dp0
set OUT=%TEMP%\wcp_tshead
if not exist "%OUT%" mkdir "%OUT%"
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
"%CSC%" /nologo /target:exe /langversion:5 /codepage:65001 ^
 /out:"%OUT%\TakeoverScopeTestHead.exe" ^
 "D:\ATooManyLanguage\MultiLanguage\mod_host\tests\TakeoverScopeTest.cs" ^
 "%HERE%TakeoverScope.cs" "%HERE%BookPool.cs" > "%HERE%head_csc.out.txt" 2>&1
if errorlevel 1 (echo HEAD COMPILE FAILED & type "%HERE%head_csc.out.txt" & exit /b 1)
echo HEAD COMPILE OK
"%OUT%\TakeoverScopeTestHead.exe" > "%HERE%head_run.out.txt" 2>&1
echo HEAD RUN exit=%errorlevel%
endlocal
