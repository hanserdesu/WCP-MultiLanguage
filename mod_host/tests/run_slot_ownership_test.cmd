@echo off
rem Compile + run the P1-4 SlotOwnership offline harness against the real WcpHost.dll.
set HERE=%~dp0
set OUT=%TEMP%\wcphost_slotown_test
if not exist "%OUT%" mkdir "%OUT%"
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
"%CSC%" /nologo /target:exe /optimize+ /codepage:65001 ^
 /r:"%HERE%..\WcpHost.dll" ^
 /out:"%OUT%\SlotOwnershipTest.exe" ^
 "%HERE%SlotOwnershipTest.cs"
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
copy /y "%HERE%..\WcpHost.dll" "%OUT%\WcpHost.dll" >nul
"%OUT%\SlotOwnershipTest.exe"
exit /b %errorlevel%
