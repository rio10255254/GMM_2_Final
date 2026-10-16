@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"
if errorlevel 1 (
  echo.
  echo Portable Agent Environment install failed.
  exit /b 1
)
echo.
echo Portable Agent Environment install complete.
echo Run verify.ps1 if you want a full post-install check.
endlocal
