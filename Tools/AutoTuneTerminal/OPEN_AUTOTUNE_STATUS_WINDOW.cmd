@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Close-AutoTuneMonitorWindows.ps1" -Mode status
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$tools=[System.IO.Path]::GetFullPath('%~dp0');" ^
  "$pidFile=Join-Path $tools '.status_window.pid';" ^
  "$p=Start-Process cmd -ArgumentList '/k', ('cd /d ' + $tools + ' && WATCH_AUTOTUNE_STATUS.cmd') -PassThru;" ^
  "Set-Content $pidFile $p.Id -Encoding ASCII;"
endlocal
