@echo off
rem Build + run probes/fpbench/probe5.cs
rem   -- BookRegistry.FingerprintOf 的成本拆解与两个等价优化的收益对比
rem 无参数 = 用内置默认（ru 词表 + 仓库 WcpHost.dll + manifest 指纹）。
rem Usage: run_probe5.cmd [tsv] [wcpDll] [expectedFingerprint] [searchDir] [rounds]
setlocal
set GAME=E:\Steam\steamapps\common\WCP-WordGirlgriend
set MGD=%GAME%\wcp_Data\Managed
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set CSC=%FW%\csc.exe
set HERE=%~dp0

set TSV=%~1
if "%TSV%"=="" set TSV=D:\ATooManyLanguage\MultiLanguage\languages\ru\output\ru_db_payload\ru_pron.tsv
set DLL=%~2
if "%DLL%"=="" set DLL=D:\ATooManyLanguage\MultiLanguage\mod_host\WcpHost.dll
set EXPECT=%~3
if "%EXPECT%"=="" set EXPECT=dfecb0ab75e9b3ef75aedd47c677d68594b060bfbb84cc6bd94efd7888f4b74e
set SEARCH=%~4
if "%SEARCH%"=="" set SEARCH=%GAME%\BepInEx\core;%MGD%
set ROUNDS=%~5
if "%ROUNDS%"=="" set ROUNDS=5

del /q "%HERE%probe5.rsp" 2> nul
>>"%HERE%probe5.rsp" echo /nologo
>>"%HERE%probe5.rsp" echo /target:exe
>>"%HERE%probe5.rsp" echo /langversion:5
>>"%HERE%probe5.rsp" echo /codepage:65001
>>"%HERE%probe5.rsp" echo /nowarn:0436,1685
>>"%HERE%probe5.rsp" echo /r:"%FW%\System.dll"
>>"%HERE%probe5.rsp" echo /r:"%FW%\System.Core.dll"
>>"%HERE%probe5.rsp" echo /r:"%MGD%\netstandard.dll"
>>"%HERE%probe5.rsp" echo /out:"%HERE%probe5.exe"
>>"%HERE%probe5.rsp" echo "%HERE%probe5.cs"

"%CSC%" @"%HERE%probe5.rsp" > "%HERE%probe5_build.txt" 2>&1
if errorlevel 1 (echo CSC FAILED & type "%HERE%probe5_build.txt" & exit /b 1)

"%HERE%probe5.exe" "%HERE%probe5_out.txt" "%TSV%" "%DLL%" "%EXPECT%" "%SEARCH%" %ROUNDS%
endlocal
