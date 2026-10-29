@echo off
cd /d "%~dp0"
python -B results\runtime_control\request_switch.py --device cuda --threads 24
pause
