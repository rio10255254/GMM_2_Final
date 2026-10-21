@echo off
setlocal
for %%I in ("%~dp0.") do set "ROOT=%%~fI"
set "LAUNCHER="
for /d %%D in ("%ROOT%\*") do (
    if exist "%%~fD\GeoEdge_AutoLauncher.ps1" set "LAUNCHER=%%~fD\GeoEdge_AutoLauncher.ps1"
)
if not defined LAUNCHER goto :missing
powershell -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" -Action train-full
goto :end
:missing
echo [ERROR] Cannot find GeoEdge_AutoLauncher.ps1
:end
echo.
pause

