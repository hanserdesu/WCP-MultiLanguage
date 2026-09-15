@echo off
rem Elevated helper: kill WCP game and relaunch it via Steam so the
rem updated BepInEx plugin (with self-test) gets loaded.
taskkill /IM wcp.exe /F
timeout /t 3 /nobreak >nul
start "" "steam://rungameid/1981560"
echo done
