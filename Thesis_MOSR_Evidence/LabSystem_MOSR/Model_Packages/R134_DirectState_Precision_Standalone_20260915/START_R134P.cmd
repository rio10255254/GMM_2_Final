@echo off

cd /d "%~dp0"

if defined R134P_PYTHON (

  "%R134P_PYTHON%" -B control.py menu

) else if exist "%USERPROFILE%\anaconda3\python.exe" (

  "%USERPROFILE%\anaconda3\python.exe" -B control.py menu

) else (

  python -B control.py menu

)

pause

