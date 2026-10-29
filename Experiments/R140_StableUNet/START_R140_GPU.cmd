@echo off
cd /d "%~dp0"
set CUBLAS_WORKSPACE_CONFIG=:4096:8
set PYTHONWARNINGS=ignore::FutureWarning
python -u -B formal\launch.py
pause
