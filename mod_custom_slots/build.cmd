@echo off
rem Build WCP Custom Slots plugin (BepInEx 5, C#5 via NETFX csc)
if "%WCP_GAME_DIR%"=="" set WCP_GAME_DIR=E:\Steam\steamapps\common\WCP-WordGirlgriend
set GAME=%WCP_GAME_DIR%
set MGD=%GAME%\wcp_Data\Managed
if not exist "%GAME%\BepInEx\core\BepInEx.dll" (
  echo Missing %GAME%\BepInEx\core\BepInEx.dll - install BepInEx first
  exit /b 1
)
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set REFS=/r:"%GAME%\BepInEx\core\BepInEx.dll" ^
 /r:"%GAME%\BepInEx\core\0Harmony.dll" ^
 /r:"%MGD%\Assembly-CSharp.dll" ^
 /r:"%MGD%\Assembly-CSharp-firstpass.dll" ^
 /r:"%MGD%\netstandard.dll" ^
 /r:"%MGD%\mscorlib.dll" ^
 /r:"%MGD%\System.dll" ^
 /r:"%MGD%\System.Core.dll" ^
 /r:"%MGD%\UnityEngine.dll" ^
 /r:"%MGD%\UnityEngine.CoreModule.dll" ^
 /r:"%MGD%\UnityEngine.UIModule.dll" ^
 /r:"%MGD%\UnityEngine.UI.dll" ^
 /r:"%MGD%\UnityEngine.TextRenderingModule.dll" ^
 /r:"%MGD%\UnityEngine.JSONSerializeModule.dll"
"%CSC%" /nologo /noconfig /nostdlib+ /target:library /langversion:5 /optimize+ /codepage:65001 %REFS% ^
 /out:"%~dp0CustomSlotsMod.dll" "%~dp0CustomSlotModel.cs" "%~dp0CustomSlotsMod.cs"
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
echo BUILD OK
if "%WCP_NO_DEPLOY%"=="1" (
  echo DEPLOY SKIPPED ^(WCP_NO_DEPLOY=1^)
  exit /b 0
)
copy /y "%~dp0CustomSlotsMod.dll" "%GAME%\BepInEx\plugins\CustomSlotsMod.dll" >nul
if errorlevel 1 (
  echo DEPLOY FAILED - game is probably running ^(dll locked^)
  exit /b 1
)
echo DEPLOYED to BepInEx\plugins
