@echo off
powershell.exe -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\monitor_training.ps1" -RefreshSeconds 3
