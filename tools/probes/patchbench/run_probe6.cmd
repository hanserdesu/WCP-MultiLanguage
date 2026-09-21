@echo off
rem Build + run probes/patchbench/probe6.cs
rem   -- 量化 HostPatches.InstallFeatures（实机 补丁:Sync = 1827ms）的成本构成
rem 无参数 = 用内置默认。Usage: run_probe6.cmd [coreDir] [managedDir] [wcpDll]
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set MGD=%GAME%\wcp_Data\Managed
set CORE=%GAME%\BepInEx\core
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set CSC=%FW%\csc.exe
set HERE=%~dp0

set COREARG=%~1
if "%COREARG%"=="" set COREARG=%CORE%
set MGDARG=%~2
if "%MGDARG%"=="" set MGDARG=%MGD%
set DLLARG=%~3
if "%DLLARG%"=="" set DLLARG=D:\ATooManyLanguage\MultiLanguage\mod_host\WcpHost.dll

del /q "%HERE%probe6.rsp" 2> nul
>>"%HERE%probe6.rsp" echo /nologo
>>"%HERE%probe6.rsp" echo /target:exe
>>"%HERE%probe6.rsp" echo /langversion:5
>>"%HERE%probe6.rsp" echo /codepage:65001
>>"%HERE%probe6.rsp" echo /nowarn:0436,1685
>>"%HERE%probe6.rsp" echo /r:"%FW%\System.dll"
>>"%HERE%probe6.rsp" echo /r:"%FW%\System.Core.dll"
>>"%HERE%probe6.rsp" echo /r:"%MGD%\netstandard.dll"
>>"%HERE%probe6.rsp" echo /r:"%CORE%\0Harmony.dll"
>>"%HERE%probe6.rsp" echo /out:"%HERE%probe6.exe"
>>"%HERE%probe6.rsp" echo "%HERE%probe6.cs"

"%CSC%" @"%HERE%probe6.rsp" > "%HERE%probe6_build.txt" 2>&1
if errorlevel 1 (echo CSC FAILED & type "%HERE%probe6_build.txt" & exit /b 1)

"%HERE%probe6.exe" "%HERE%probe6_out.txt" "%COREARG%" "%MGDARG%" "%DLLARG%"
endlocal
