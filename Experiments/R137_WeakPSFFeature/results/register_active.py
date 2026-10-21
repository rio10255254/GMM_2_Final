from pathlib import Path
import json,shutil
P=Path(r'D:\GMM_2_Final\Experiments\R137_WeakPSFFeature');repo=P.parents[1]
shutil.copy2(repo/'Experiments/R130_Clean/requirements.txt',P/'requirements.txt')
readme=P/'README.md';s=readme.read_text(encoding='utf-8').replace('狀態：建立與測試中，尚未正式訓練。','狀態：前置檢查通過，正式8192次訓練執行中；完成後自動驗證930張影像。')
s+='\n## 手動操作\n\nSTART_R137.cmd 啟動整個流程；已完成時不覆寫。CHECK_STATUS.cmd 只讀目前狀態。正式訓練中請勿重複啟動；中斷時會保留已完成模型與記錄，不自動重新訓練或接受不同來源。\n\n最終結果入口：reports/R137_RESULTS.md，完成後才出現。完整步數、輸出檔及查核齊全才會記為完成。PSF開關測試與新模型對R130比較分開解讀，新增局部轉換參數也是模型變化的一部分。\n'
readme.write_text(s,encoding='utf-8')
(P/'CHECK_STATUS.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\n"C:\\Users\\Rio\\anaconda3\\python.exe" -c "from pathlib import Path; names=[\'runs/pipeline_status.json\',\'runs/formal_8192/status.json\',\'results/reconstruction_status.json\',\'results/complete.json\',\'runs/pipeline_failure.json\']; [print(n,Path(n).read_text(encoding=\'utf-8-sig\')) for n in names if Path(n).exists()]"\r\npause\r\n',encoding='ascii')
state=repo/'PROJECT_STATE.md';v=state.read_text(encoding='utf-8-sig');marker='<!-- R137_WEAK_PSF_20260921 -->';assert marker not in v
v=v.replace('### Open Research / Side Tracks','### Open Research / Side Tracks\n'+marker+'\nR137弱PSF測試執行中（2026-09-21）：依使用者授權沿用既有25顆PSF，固定平均、特徵層強度0.02，獨立scratch8192次。前置光學公式、實際PSF影響、精確關閉及固定光學線索下分塊/梯度檢查通過；尚未完成真實效果比較。原R130與正式基準保留。 [執行入口](Experiments/R137_WeakPSFFeature/README.md)\n',1);state.write_text(v,encoding='utf-8')
idx=repo/'Experiments/INDEX.md';v=idx.read_text(encoding='utf-8-sig');v+='\n## R137 Weak PSF Feature 20260921\n\n獨立8192次scratch與930影像驗證執行中，固定舊25PSF弱特徵輔助0.02；結果尚未完成，不升級基準。[R137](R137_WeakPSFFeature/README.md)\n';idx.write_text(v,encoding='utf-8')
print('Manual status entry and active experiment registration created; frozen execution files untouched')
