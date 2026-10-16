@echo off
cd /d "%~dp0"
set CUBLAS_WORKSPACE_CONFIG=:4096:8
set PYTHONWARNINGS=ignore::FutureWarning
"C:\Users\Rio\anaconda3\python.exe" -u -B formal\launch.py
pause
