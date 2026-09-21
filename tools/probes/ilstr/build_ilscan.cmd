@echo off
rem Build probes/ilstr/ilscan.cs with the desktop .NET Framework only.
setlocal
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set FW=C:\Windows\Microsoft.NET\Framework64\v4.0.30319
set HERE=%~dp0
"%CSC%" /nologo /noconfig /target:exe /langversion:5 /codepage:65001 /r:"%FW%\System.dll" /r:"%FW%\System.Core.dll" /out:"%HERE%ilscan.exe" "%HERE%ilscan.cs"
echo EXITCODE=%ERRORLEVEL%
endlocal
