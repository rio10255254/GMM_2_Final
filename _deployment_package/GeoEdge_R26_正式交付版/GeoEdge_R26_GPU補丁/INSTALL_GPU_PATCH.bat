@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_GPU_PATCH.ps1" %*
echo.
pause
