@echo off
rem Build WCP unified host (BepInEx 5, C#5 via NETFX csc).
rem v0.3.0: per-book pool isolation (BookPool) + shared host patches and scoped runtime.
rem Override game dir with WCP_GAME_DIR; WCP_NO_DEPLOY=1 builds without deploying.
setlocal
set HERE=%~dp0
if "%WCP_GAME_DIR%"=="" set WCP_GAME_DIR=E:\Steam\steamapps\common\WCP-WordGirlgriend
set GAME=%WCP_GAME_DIR%
set MGD=%GAME%\wcp_Data\Managed
if not exist "%GAME%\BepInEx\core\BepInEx.dll" (
  echo Missing %GAME%\BepInEx\core\BepInEx.dll - install BepInEx first
  exit /b 1
)
if not exist "%MGD%\Assembly-CSharp.dll" (
  echo Missing %MGD%\Assembly-CSharp.dll - wrong game dir: %GAME%
  exit /b 1
)
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set REFS=/r:"%GAME%\BepInEx\core\BepInEx.dll" ^
 /r:"%GAME%\BepInEx\core\0Harmony.dll" ^
 /r:"%MGD%\netstandard.dll" ^
 /r:"%MGD%\mscorlib.dll" ^
 /r:"%MGD%\System.dll" ^
 /r:"%MGD%\System.Core.dll" ^
 /r:"%MGD%\System.Data.dll" ^
 /r:"%MGD%\Mono.Data.Sqlite.dll" ^
 /r:"%MGD%\Assembly-CSharp.dll" ^
 /r:"%MGD%\Assembly-CSharp-firstpass.dll" ^
 /r:"%MGD%\UnityEngine.dll" ^
 /r:"%MGD%\UnityEngine.AudioModule.dll" ^
 /r:"%MGD%\UnityEngine.CoreModule.dll" ^
 /r:"%MGD%\UnityEngine.UnityWebRequestModule.dll" ^
 /r:"%MGD%\UnityEngine.UnityWebRequestAudioModule.dll" ^
 /r:"%MGD%\UnityEngine.UIModule.dll" ^
 /r:"%MGD%\UnityEngine.UI.dll" ^
 /r:"%MGD%\UnityEngine.TextRenderingModule.dll" ^
 /r:"%MGD%\Unity.TextMeshPro.dll"
"%CSC%" /nologo /noconfig /nostdlib+ /target:library /langversion:5 /optimize+ /codepage:65001 %REFS% ^
 /out:"%HERE%WcpHost.dll" ^
 "%HERE%AssemblyInfo.cs" ^
 "%HERE%Core\Json.cs" ^
 "%HERE%Core\Manifest.cs" ^
 "%HERE%Core\ResourceRouter.cs" ^
 "%HERE%Core\ILanguageStrategy.cs" ^
 "%HERE%Core\StrategyContext.cs" ^
 "%HERE%Core\BookPool.cs" ^
 "%HERE%Core\GameLearnedStats.cs" ^
 "%HERE%Core\GenericLanguageStrategy.cs" ^
 "%HERE%StrategyLoader.cs" ^
 "%HERE%GameAdapter.cs" ^
 "%HERE%TakeoverScope.cs" ^
 "%HERE%HostRuntime.cs" ^
 "%HERE%WordAudioCompat.cs" ^
 "%HERE%SentenceAudioService.cs" ^
 "%HERE%HostPatches.cs" ^
 "%HERE%Host.cs"
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
echo BUILD OK
if "%WCP_NO_DEPLOY%"=="1" (
  echo DEPLOY SKIPPED ^(WCP_NO_DEPLOY=1^)
  exit /b 0
)
copy /y "%HERE%WcpHost.dll" "%GAME%\BepInEx\plugins\WcpHost.dll" >nul
if errorlevel 1 (
  echo DEPLOY FAILED - game is probably running ^(dll locked^)
  exit /b 1
)
echo DEPLOYED to BepInEx\plugins
endlocal
