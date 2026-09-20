@echo off
rem Caller-safe wrapper for the Custom Slots source + behaviour checks.
rem
rem Why: test_custom_slots.ps1 ends with `exit 1` on failure. A .ps1 invoked with
rem `&` from another PowerShell session runs *in that session*, so the exit kills
rem the caller and its captured pipeline output is lost (observed 2026-09-18:
rem empty output files, exit=1, no diagnostics). Running it in a child process
rem isolates the exit; stdout+stderr are tee'd to slots_test_out.txt.
setlocal
set OUT=%~dp0slots_test_out.txt
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0test_custom_slots.ps1" > "%OUT%" 2>&1
set CODE=%ERRORLEVEL%
type "%OUT%"
exit /b %CODE%
