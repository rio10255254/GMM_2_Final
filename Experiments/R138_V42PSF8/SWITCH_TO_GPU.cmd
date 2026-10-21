@echo off
cd /d "%~dp0"
"C:\Users\Rio\anaconda3\python.exe" -B results\runtime_control\request_switch.py --device cuda --threads 24
pause
