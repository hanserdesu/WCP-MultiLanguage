@echo off
rem Build + run the host identity-layer regression test OUTSIDE the game.
rem The test references the same compiled WcpHost.dll used by the game, so
rem StrategyLoader can be validated against real pack assemblies as well.
rem Real inputs: packs/*/manifest.json and the live MyBook.es3 word lists.
rem Build output goes to %TEMP% (a build artifact, not source). Override with REGTEST_OUT.
setlocal
set HERE=%~dp0
if "%REGTEST_OUT%"=="" set REGTEST_OUT=%TEMP%\wcphost_regtest
if not exist "%REGTEST_OUT%" mkdir "%REGTEST_OUT%"
if "%WCP_GAME_DIR%"=="" set WCP_GAME_DIR=E:\Steam\steamapps\common\WCP-WordGirlgriend
set MGD=%WCP_GAME_DIR%\wcp_Data\Managed
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%HERE%..\WcpHost.dll" (
  echo Missing mod_host\WcpHost.dll - build the host first
  exit /b 1
)
"%CSC%" /nologo /target:exe /optimize+ /codepage:65001 ^
 /r:"%HERE%..\WcpHost.dll" ^
 /out:"%REGTEST_OUT%\RegistryTest.exe" ^
 "%HERE%RegistryTest.cs"
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
copy /y "%HERE%..\WcpHost.dll" "%REGTEST_OUT%\WcpHost.dll" >nul
if errorlevel 1 (echo COPY FAILED & exit /b 1)
if exist "%MGD%\Mono.Data.Sqlite.dll" copy /y "%MGD%\Mono.Data.Sqlite.dll" "%REGTEST_OUT%\Mono.Data.Sqlite.dll" >nul
if exist "%WCP_GAME_DIR%\wcp_Data\Plugins\x86_64\sqlite3.dll" copy /y "%WCP_GAME_DIR%\wcp_Data\Plugins\x86_64\sqlite3.dll" "%REGTEST_OUT%\sqlite3.dll" >nul
rem packs 根默认取本仓库的 packs\（tests\..\..\packs）；第一个显式参数可覆盖。
set "PACKS_ARG=%HERE%..\..\packs"
if not "%~1"=="" set "PACKS_ARG=%~1"
echo BUILD OK
"%REGTEST_OUT%\RegistryTest.exe" "%PACKS_ARG%"
exit /b %errorlevel%
