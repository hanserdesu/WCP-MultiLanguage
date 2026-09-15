@echo off
rem Double-click launcher: re-download only the resources whose SHA-256 differs
rem from what is recorded in hub-state.json (defaults to the installed books).
if /i not "%~1"=="--keep-open" (
    cmd.exe /d /k call "%~f0" --keep-open
    exit /b %ERRORLEVEL%
)
setlocal EnableExtensions
title WCP Wordbook Hub - Update Resources
set "HERE=%~dp0"
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "PS_EXE=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" set "PS_EXE=pwsh.exe"
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%HERE%Install-WCP-Wordbooks.ps1" -Update
exit /b %ERRORLEVEL%
