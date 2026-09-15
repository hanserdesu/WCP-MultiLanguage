@echo off
rem Build WCP Sentence Audio plugin (BepInEx 5, C#5 via NETFX csc)
rem Override game dir with WCP_GAME_DIR; default is the live install.
rem KEEP THIS FILE ASCII-ONLY: cmd.exe reads .cmd using the ANSI codepage, so a
rem UTF-8 CJK comment gets mangled and can swallow the following ASCII bytes
rem (observed 2026-09-14: a Chinese rem line produced "'o'/'P_GAME_DIR' is not
rem recognized as an internal or external command" noise on every build).
if "%WCP_GAME_DIR%"=="" set WCP_GAME_DIR=E:\Steam\steamapps\common\WCP-WordGirlgriend
set GAME=%WCP_GAME_DIR%
set MGD=%GAME%\wcp_Data\Managed
if not exist "%MGD%\mscorlib.dll" (
  echo Missing %MGD%\mscorlib.dll - wrong game dir: %GAME%
  exit /b 1
)
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set REFS=/r:"%GAME%\BepInEx\core\BepInEx.dll" ^
 /r:"%GAME%\BepInEx\core\0Harmony.dll" ^
 /r:"%MGD%\netstandard.dll" ^
 /r:"%MGD%\mscorlib.dll" ^
 /r:"%MGD%\System.dll" ^
 /r:"%MGD%\System.Core.dll" ^
 /r:"%MGD%\Assembly-CSharp.dll" ^
 /r:"%MGD%\Assembly-CSharp-firstpass.dll" ^
 /r:"%MGD%\UnityEngine.dll" ^
 /r:"%MGD%\UnityEngine.CoreModule.dll" ^
 /r:"%MGD%\UnityEngine.UIModule.dll" ^
 /r:"%MGD%\UnityEngine.AudioModule.dll" ^
 /r:"%MGD%\UnityEngine.UnityWebRequestModule.dll" ^
 /r:"%MGD%\UnityEngine.UnityWebRequestAudioModule.dll" ^
 /r:"%MGD%\UnityEngine.UI.dll" ^
 /r:"%MGD%\UnityEngine.TextRenderingModule.dll" ^
 /r:"%MGD%\Unity.TextMeshPro.dll"
"%CSC%" /nologo /noconfig /nostdlib+ /target:library /langversion:5 /optimize+ %REFS% ^
 /out:"%~dp0SentenceAudioMod.dll" "%~dp0SentenceAudioMod.cs" "%~dp0..\mod_book_name\BookProfiles.cs"
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
echo BUILD OK
if "%WCP_NO_DEPLOY%"=="1" (
  echo DEPLOY SKIPPED ^(WCP_NO_DEPLOY=1^)
  exit /b 0
)
copy /y "%~dp0SentenceAudioMod.dll" "%GAME%\BepInEx\plugins\SentenceAudioMod.dll" >nul
if errorlevel 1 (
  echo DEPLOY FAILED - game is probably running ^(dll locked^)
  exit /b 1
)
echo DEPLOYED to BepInEx\plugins
