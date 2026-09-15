@echo off
if /i not "%~1"=="--keep-open" (
    cmd.exe /d /k call "%~f0" --keep-open
    exit /b %ERRORLEVEL%
)
setlocal EnableExtensions
title WCP Japanese One-Click Installer

set "ROOT=%~dp0"
set "SUPPORT=%ROOT%support"
if not exist "%SUPPORT%\run-installer.ps1" set "SUPPORT=%ROOT%"
set "STARTUP_LOG=%ROOT%installer-startup.log"
>>"%STARTUP_LOG%" echo [%date% %time%] Installer started.

echo ========================================
echo   WCP Japanese one-click installer
echo   Double-click this file only.
echo ========================================
echo.

set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "PS_EXE=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
call :TestPowerShell "%PS_EXE%"
if not errorlevel 1 goto RunWindowsPowerShell

where pwsh.exe >nul 2>&1
if errorlevel 1 goto CompatibilityHelp
set "PS_EXE=pwsh.exe"
call :TestPowerShell "%PS_EXE%"
if not errorlevel 1 goto RunPowerShell7

:CompatibilityHelp
>>"%STARTUP_LOG%" echo [%date% %time%] No compatible PowerShell was found.
call "%SUPPORT%\compatibility-help.cmd"
exit /b %ERRORLEVEL%

:RunWindowsPowerShell
echo Using Windows PowerShell compatibility mode.
>>"%STARTUP_LOG%" echo [%date% %time%] Using Windows PowerShell: %PS_EXE%
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -NoExit -File "%SUPPORT%\run-installer.ps1" -HostLabel "Windows PowerShell"
exit /b %ERRORLEVEL%

:RunPowerShell7
echo Using PowerShell 7 compatibility mode.
>>"%STARTUP_LOG%" echo [%date% %time%] Using PowerShell 7.
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -NoExit -File "%SUPPORT%\run-installer.ps1" -HostLabel "PowerShell 7"
exit /b %ERRORLEVEL%

:TestPowerShell
if not exist "%SUPPORT%\check-compatibility.ps1" exit /b 1
"%~1" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SUPPORT%\check-compatibility.ps1" >nul 2>&1
exit /b %ERRORLEVEL%
