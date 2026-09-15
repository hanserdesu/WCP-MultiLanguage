@echo off
rem Build the Japanese language pack strategy. This only writes packs\ja\*.dll;
rem it never deploys to the game directory.
setlocal
set HERE=%~dp0
if "%WCP_GAME_DIR%"=="" set WCP_GAME_DIR=E:\Steam\steamapps\common\WCP-WordGirlgriend
set GAME=%WCP_GAME_DIR%
set MGD=%GAME%\wcp_Data\Managed
if not exist "%HERE%..\WcpHost.dll" (
  echo Missing mod_host\WcpHost.dll - build the host first
  exit /b 1
)
if not exist "%MGD%\Mono.Data.Sqlite.dll" (
  echo Missing %MGD%\Mono.Data.Sqlite.dll - wrong game dir: %GAME%
  exit /b 1
)
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set REFS=/r:"%HERE%..\WcpHost.dll" ^
 /r:"%MGD%\netstandard.dll" ^
 /r:"%MGD%\mscorlib.dll" ^
 /r:"%MGD%\System.dll" ^
 /r:"%MGD%\System.Core.dll" ^
 /r:"%MGD%\System.Data.dll" ^
 /r:"%MGD%\Mono.Data.Sqlite.dll"
"%CSC%" /nologo /noconfig /nostdlib+ /target:library /langversion:5 /optimize+ /codepage:65001 %REFS% ^
 /out:"%HERE%..\..\packs\ja\WcpPack.Ja.dll" ^
 "%HERE%JapaneseStrategy.cs"
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
echo BUILD OK: packs\ja\WcpPack.Ja.dll
endlocal
