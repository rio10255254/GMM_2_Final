@echo off
cd /d "%~dp0"
if exist "results\complete.json" (
  echo This run is complete. Existing results will not be overwritten.
  echo Read reports\R130_CLEAN_RESULTS.md or use infer_r130_clean.py.
  pause
  exit /b 0
)
if exist "runs\formal_8192" (
  echo A formal run already exists. Do not launch duplicate training.
  echo Check runs\pipeline_status.json and runs\formal_8192\status.json.
  pause
  exit /b 0
)
python -B scripts\launch_r130.py
pause
