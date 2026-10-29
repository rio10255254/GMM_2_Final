@echo off
cd /d "%~dp0"
set CUDA_VISIBLE_DEVICES=-1
set PYTHONWARNINGS=ignore::FutureWarning
python -u -B results\runtime_control\supervise.py
pause
