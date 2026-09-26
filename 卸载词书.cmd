@echo off
rem Uninstall selected Hub-managed wordbook resources while preserving game saves.
if /i not "%~1"=="--keep-open" (
    cmd.exe /d /k call "%~f0" --keep-open
    exit /b %ERRORLEVEL%
)
setlocal EnableExtensions
title WCP Wordbook Hub - Uninstall Wordbooks

set "HERE=%~dp0"
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "PS_EXE=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" set "PS_EXE=pwsh.exe"
set "WCP_KEEP_OPEN=1"
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%HERE%run-installer.ps1" -Uninstall
exit /b %ERRORLEVEL%
