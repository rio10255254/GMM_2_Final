@echo off

cd /d "%~dp0"

if defined R129_PYTHON (

  "%R129_PYTHON%" -B control.py menu

) else if exist "%USERPROFILE%\anaconda3\python.exe" (

  "%USERPROFILE%\anaconda3\python.exe" -B control.py menu

) else (

  python -B control.py menu

)

pause

