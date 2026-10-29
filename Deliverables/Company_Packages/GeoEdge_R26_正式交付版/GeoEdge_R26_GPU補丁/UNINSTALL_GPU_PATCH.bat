@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0UNINSTALL_GPU_PATCH.ps1" %*
echo.
pause
