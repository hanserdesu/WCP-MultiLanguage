@echo off
rem Build + run probes/es3bench/probe3.cs -- real-ES3 offline A/B, compile-time refs.
rem Usage: run_probe3.cmd <src.es3> <workdir> [nKeys]
rem csc is fed a response file because cmd.exe caps a command line at 8191 chars.
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set MGD=%GAME%\wcp_Data\Managed
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set CSC=%FW%\csc.exe
set HERE=%~dp0
if not exist "%HERE%Mono.Cecil.dll" copy /y "%GAME%\BepInEx\core\Mono.Cecil.dll" "%HERE%Mono.Cecil.dll" > nul

rem The game's assemblies reference netstandard 2.1; desktop .NET Framework only ships a
rem 2.0 facade. Redirect 2.1 -> 2.0 so BCL types forward to the desktop mscorlib instead
rem of a Unity-only facade that cannot provide them.
del /q "%HERE%probe3.exe.config" 2> nul
>>"%HERE%probe3.exe.config" echo ^<?xml version="1.0" encoding="utf-8"?^>
>>"%HERE%probe3.exe.config" echo ^<configuration^>
>>"%HERE%probe3.exe.config" echo   ^<runtime^>
>>"%HERE%probe3.exe.config" echo     ^<assemblyBinding xmlns="urn:schemas-microsoft-com:asm.v1"^>
>>"%HERE%probe3.exe.config" echo       ^<dependentAssembly^>
>>"%HERE%probe3.exe.config" echo         ^<assemblyIdentity name="netstandard" publicKeyToken="cc7b13ffcd2ddd51" culture="neutral" /^>
>>"%HERE%probe3.exe.config" echo         ^<bindingRedirect oldVersion="0.0.0.0-2.1.0.0" newVersion="2.0.0.0" /^>
>>"%HERE%probe3.exe.config" echo       ^</dependentAssembly^>
>>"%HERE%probe3.exe.config" echo     ^</assemblyBinding^>
>>"%HERE%probe3.exe.config" echo   ^</runtime^>
>>"%HERE%probe3.exe.config" echo ^</configuration^>

del /q "%HERE%probe3.rsp" 2> nul
>>"%HERE%probe3.rsp" echo /nologo
>>"%HERE%probe3.rsp" echo /target:exe
>>"%HERE%probe3.rsp" echo /langversion:5
>>"%HERE%probe3.rsp" echo /codepage:65001
>>"%HERE%probe3.rsp" echo /nowarn:0436,1685
>>"%HERE%probe3.rsp" echo /r:"%FW%\System.dll"
>>"%HERE%probe3.rsp" echo /r:"%FW%\System.Core.dll"
>>"%HERE%probe3.rsp" echo /r:"%GAME%\BepInEx\core\Mono.Cecil.dll"
>>"%HERE%probe3.rsp" echo /r:"%MGD%\netstandard.dll"
>>"%HERE%probe3.rsp" echo /r:"%MGD%\Assembly-CSharp-firstpass.dll"
>>"%HERE%probe3.rsp" echo /r:"%MGD%\UnityEngine.CoreModule.dll"
>>"%HERE%probe3.rsp" echo /r:"%MGD%\UnityEngine.AudioModule.dll"
>>"%HERE%probe3.rsp" echo /r:"%MGD%\UnityEngine.UIModule.dll"
>>"%HERE%probe3.rsp" echo /r:"%MGD%\UnityEngine.AnimationModule.dll"
>>"%HERE%probe3.rsp" echo /r:"%MGD%\UnityEngine.ImageConversionModule.dll"
>>"%HERE%probe3.rsp" echo /r:"%MGD%\UnityEngine.UnityWebRequestModule.dll"
>>"%HERE%probe3.rsp" echo /r:"%MGD%\UnityEngine.UnityWebRequestAudioModule.dll"
>>"%HERE%probe3.rsp" echo /out:"%HERE%probe3.exe"
>>"%HERE%probe3.rsp" echo "%HERE%probe3.cs"

"%CSC%" @"%HERE%probe3.rsp" > "%HERE%probe3_build.txt" 2>&1
if errorlevel 1 (echo CSC FAILED & type "%HERE%probe3_build.txt" & exit /b 1)
if "%~3"=="" (set NK=45) else (set NK=%~3)
"%HERE%probe3.exe" "%HERE%probe3_out.txt" "%~1" "%~2" "%MGD%" %NK%
type "%HERE%probe3_out.txt"
endlocal
