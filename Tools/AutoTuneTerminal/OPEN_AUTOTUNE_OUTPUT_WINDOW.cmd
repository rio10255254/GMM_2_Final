@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Close-AutoTuneMonitorWindows.ps1" -Mode output
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$tools=[System.IO.Path]::GetFullPath('%~dp0');" ^
  "$pidFile=Join-Path $tools '.output_window.pid';" ^
  "$p=Start-Process cmd -ArgumentList '/k', ('cd /d ' + $tools + ' && WATCH_AUTOTUNE_OUTPUT.cmd') -PassThru;" ^
  "Set-Content $pidFile $p.Id -Encoding ASCII;"
endlocal
