# R82 檔案說明

- `config/experiment.json`：在看到 R82 輸出前鎖定的模型、資料、規則與證據資格。
- `scripts/run_r82.py`：完整執行入口與資料完整性檢查。
- `scripts/infer_r82.py`：依各模型原本的正式推論方式產生同批重建影像。
- `scripts/run_acm_multimethod.m`：200 張合成顯微影像的多模型 ACM 輪廓抽取。
- `scripts/run_sem_acm_multimethod.m`：36 顆 SEM 真值的多模型 ACM 輪廓抽取。
- `scripts/analyze_r82.py`：配對統計、場景比較、圖表與中文報告。
- `scripts/validate_r82.py`：交付前完整性與數字一致性檢查。
- `results/reconstructions`：本輪重建影像，依資料組與模型分開。
- `results/tables`：逐張、逐 pillar、逐位移配對與彙總表。
- `results/figures`：固定案例與總覽圖，不作人工挑圖計分。
- `reports/R82_RESULTS_TW.md`：最後可讀結論。
