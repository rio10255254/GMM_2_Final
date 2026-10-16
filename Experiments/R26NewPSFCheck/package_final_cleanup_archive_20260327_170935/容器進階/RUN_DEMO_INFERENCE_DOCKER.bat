@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "LAUNCHER="
for /d %%D in ("%ROOT%\*") do (
    if exist "%%~fD\GeoEdge_Launcher.ps1" set "LAUNCHER=%%~fD\GeoEdge_Launcher.ps1"
)
if not defined LAUNCHER goto :missing
powershell -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" -Action infer-demo
goto :end
:missing
echo [ERROR] Cannot find GeoEdge_Launcher.ps1
:end
echo.
pause

