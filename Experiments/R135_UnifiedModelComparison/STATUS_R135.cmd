@echo off
chcp 65001 >nul
python -B "%~dp0scripts\status.py"
pause
