# R80 檔案角色

- `config/experiment.json`：在查看完整輸出前鎖定的模型、資料、判定規則與檔案雜湊。
- `scripts/run_r80.py`：完整自動執行入口。
- `scripts/analyze_r80.py`：將所有表格整合成最終判定、圖與中文報告。
- `scripts/run_acm_multimethod.m`：沿用 R73/R74 的 Chan–Vese ACM 方法，同時處理 Raw、第 23 輪與第 100 輪。
- `tests/test_r80.py`：檢查樣本數、配對一致性、結果完整性與結論邏輯。
- `results/`：重建影像、逐張數值、輪廓結果、圖與執行紀錄。
- `reports/R80_RESULTS_TW.md`：面向研究判斷的中文完整報告。

來源資料與 R79 權重均只讀引用，不複製、不改名，也不寫回上游實驗。
