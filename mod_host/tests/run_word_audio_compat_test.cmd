@echo off
rem Offline harness for WordAudioCompat (pure logic, no Unity dependency).
rem
rem Why a .cmd wrapper in addition to the .ps1: the .ps1 ends with
rem `exit $LASTEXITCODE`, and a .ps1 invoked with & from another PowerShell
rem session runs *in that session* -- so the exit kills the caller and its
rem captured output is lost. This wrapper is caller-safe: it builds into TEMP,
rem runs the exe, and returns the harness exit code.
setlocal
set T=%TEMP%\wcp-wordaudio-compat
if not exist "%T%" mkdir "%T%"
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
"%CSC%" /nologo /target:exe /langversion:5 /codepage:65001 ^
  /out:"%T%\WordAudioCompatTest.exe" ^
  "%~dp0WordAudioCompatTest.cs" "%~dp0..\WordAudioCompat.cs"
if errorlevel 1 (
  echo BUILD FAILED
  exit /b 1
)
"%T%\WordAudioCompatTest.exe" > "%~dp0wac_out.txt" 2>&1
type "%~dp0wac_out.txt"
exit /b %ERRORLEVEL%
