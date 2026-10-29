@echo off
cd /d "%~dp0"
python -c "from pathlib import Path; names=['runs/pipeline_status.json','runs/formal_8192/status.json','results/reconstruction_status.json','results/complete.json','runs/pipeline_failure.json']; [print(n,Path(n).read_text(encoding='utf-8-sig')) for n in names if Path(n).exists()]"
pause
