@echo off
rem Double-click launcher for the unified WCP wordbook installer.
rem Keep this file ASCII-only: cmd.exe reads batch files with the console code
rem page, so non-ASCII text here would render as mojibake.  All Chinese UI text
rem lives in the UTF-8 (BOM) PowerShell scripts.
if /i not "%~1"=="--keep-open" (
    cmd.exe /d /k call "%~f0" --keep-open
    exit /b %ERRORLEVEL%
)
setlocal EnableExtensions
title WCP Wordbook Hub - Install / Update
set "HERE=%~dp0"
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "PS_EXE=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" set "PS_EXE=pwsh.exe"
rem Reaching this line means the keep-open shell is active (see the --keep-open
rem branch above), so tell the launcher to promise the window stays open.
set "WCP_KEEP_OPEN=1"
rem Always go through run-installer.ps1: it injects the installer version that
rem the self-update check compares against, and expands the real error chain.
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%HERE%run-installer.ps1"
exit /b %ERRORLEVEL%
