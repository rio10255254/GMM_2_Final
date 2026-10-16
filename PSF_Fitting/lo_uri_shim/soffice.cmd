@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0soffice_wrapper.ps1" %*
exit /b %errorlevel%
