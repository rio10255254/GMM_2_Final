@echo off
setlocal
echo [INFO] GeoEdge R26 startup
echo [INFO] Host Python is preferred. If GPU runtime is needed later, install the offline GPU patch.
echo [INFO] Docker / WSL is only the last fallback.
echo.
for %%I in ("%~dp0.") do set "ROOT=%%~fI"
set "LAUNCHER="
for /d %%D in ("%ROOT%\*") do (
    if exist "%%~fD\GeoEdge_AutoLauncher.ps1" set "LAUNCHER=%%~fD\GeoEdge_AutoLauncher.ps1"
)
if not defined LAUNCHER goto :missing
powershell -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" -Action first-run
if errorlevel 1 goto :end
powershell -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" -Action menu
goto :end
:missing
echo [ERROR] Cannot find GeoEdge_AutoLauncher.ps1
:end
echo.
pause

