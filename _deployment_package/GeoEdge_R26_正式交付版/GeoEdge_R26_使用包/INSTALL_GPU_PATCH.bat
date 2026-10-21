@echo off
setlocal
echo [INFO] This launcher expects the offline GPU patch package.
echo [INFO] If GeoEdge_R26_GPU?? exists next to this package, it will be used automatically.
set "PATCH_DIR=%~dp0..\GeoEdge_R26_GPU??"
if exist "%PATCH_DIR%\INSTALL_GPU_PATCH.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PATCH_DIR%\INSTALL_GPU_PATCH.ps1" -TargetPackageRoot "%~dp0"
  goto :end
)
echo [WARN] Default patch folder not found: %PATCH_DIR%
set /p PATCH_DIR=Enter extracted GPU patch folder path: 
if not exist "%PATCH_DIR%\INSTALL_GPU_PATCH.ps1" (
  echo [ERROR] INSTALL_GPU_PATCH.ps1 not found in patch folder.
  goto :end
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PATCH_DIR%\INSTALL_GPU_PATCH.ps1" -TargetPackageRoot "%~dp0"
:end
echo.
pause
