@echo off
setlocal
if "%~1"=="" (
  echo Usage: %~nx0 PID LOG_PATH [LABEL]
  exit /b 1
)
if "%~2"=="" (
  echo Usage: %~nx0 PID LOG_PATH [LABEL]
  exit /b 1
)
set "PID_ARG=%~1"
set "LOG_ARG=%~2"
set "LABEL_ARG=%~3"
if "%LABEL_ARG%"=="" set "LABEL_ARG=Background Run"
title %LABEL_ARG%
cd /d "%~dp0..\.."
python Model\GeoEdgeAlignSR_v1_BackgroundRunWatch.py --pid "%PID_ARG%" --log "%LOG_ARG%" --label "%LABEL_ARG%"
endlocal
