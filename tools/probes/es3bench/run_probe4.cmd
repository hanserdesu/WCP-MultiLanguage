@echo off
rem Build + run probes/es3bench/probe4.cs -- does the shipped ES3 batch Create() succeed,
rem and what do the two write arms actually cost?
rem Usage: run_probe4.cmd <liveSaveCopy> <workdir> [nKeys]
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set MGD=%GAME%\wcp_Data\Managed
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set CSC=%FW%\csc.exe
set HERE=%~dp0
if not exist "%HERE%Mono.Cecil.dll" copy /y "%GAME%\BepInEx\core\Mono.Cecil.dll" "%HERE%Mono.Cecil.dll" > nul

del /q "%HERE%probe4.exe.config" 2> nul
>>"%HERE%probe4.exe.config" echo ^<?xml version="1.0" encoding="utf-8"?^>
>>"%HERE%probe4.exe.config" echo ^<configuration^>
>>"%HERE%probe4.exe.config" echo   ^<runtime^>
>>"%HERE%probe4.exe.config" echo     ^<assemblyBinding xmlns="urn:schemas-microsoft-com:asm.v1"^>
>>"%HERE%probe4.exe.config" echo       ^<dependentAssembly^>
>>"%HERE%probe4.exe.config" echo         ^<assemblyIdentity name="netstandard" publicKeyToken="cc7b13ffcd2ddd51" culture="neutral" /^>
>>"%HERE%probe4.exe.config" echo         ^<bindingRedirect oldVersion="0.0.0.0-2.1.0.0" newVersion="2.0.0.0" /^>
>>"%HERE%probe4.exe.config" echo       ^</dependentAssembly^>
>>"%HERE%probe4.exe.config" echo     ^</assemblyBinding^>
>>"%HERE%probe4.exe.config" echo   ^</runtime^>
>>"%HERE%probe4.exe.config" echo ^</configuration^>

del /q "%HERE%probe4.rsp" 2> nul
>>"%HERE%probe4.rsp" echo /nologo
>>"%HERE%probe4.rsp" echo /target:exe
>>"%HERE%probe4.rsp" echo /langversion:5
>>"%HERE%probe4.rsp" echo /codepage:65001
>>"%HERE%probe4.rsp" echo /nowarn:0436,1685
>>"%HERE%probe4.rsp" echo /r:"%FW%\System.dll"
>>"%HERE%probe4.rsp" echo /r:"%FW%\System.Core.dll"
>>"%HERE%probe4.rsp" echo /r:"%GAME%\BepInEx\core\Mono.Cecil.dll"
>>"%HERE%probe4.rsp" echo /r:"%MGD%\netstandard.dll"
>>"%HERE%probe4.rsp" echo /r:"%MGD%\Assembly-CSharp-firstpass.dll"
>>"%HERE%probe4.rsp" echo /r:"%MGD%\UnityEngine.CoreModule.dll"
>>"%HERE%probe4.rsp" echo /out:"%HERE%probe4.exe"
>>"%HERE%probe4.rsp" echo "%HERE%probe4.cs"

"%CSC%" @"%HERE%probe4.rsp" > "%HERE%probe4_build.txt" 2>&1
if errorlevel 1 (echo CSC FAILED & type "%HERE%probe4_build.txt" & exit /b 1)
if "%~3"=="" (set NK=45) else (set NK=%~3)
"%HERE%probe4.exe" "%HERE%probe4_out.txt" "%~1" "%~2" "%MGD%" %NK%
type "%HERE%probe4_out.txt"
endlocal
