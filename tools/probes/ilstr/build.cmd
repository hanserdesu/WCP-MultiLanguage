@echo off
rem Build probes/ilstr/ilstr.cs (Mono.Cecil IL string scanner). Pure ASCII on purpose.
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set MGD=%GAME%\wcp_Data\Managed
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set HERE=%~dp0
"%CSC%" /nologo /noconfig /nostdlib+ /target:exe /langversion:5 /codepage:65001 /r:"%MGD%\mscorlib.dll" /r:"%MGD%\netstandard.dll" /r:"%MGD%\System.dll" /r:"%MGD%\System.Core.dll" /r:"%GAME%\BepInEx\core\Mono.Cecil.dll" /out:"%HERE%ilstr.exe" "%HERE%ilstr.cs"
echo EXITCODE=%ERRORLEVEL%
endlocal
