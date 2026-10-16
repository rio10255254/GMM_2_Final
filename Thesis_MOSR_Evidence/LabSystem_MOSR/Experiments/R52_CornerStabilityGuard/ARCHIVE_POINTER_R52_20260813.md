# R52 歷史封存與恢復入口

日期：2026-08-13

## 結論身分

R52 已完成 100 輪正式訓練，但真實角點守門失敗，因此是已結案的負結果，不是可採用模型，也不改變任何正式 baseline。

## 目前封存狀態

- H 槽完整快照：`H:\GMM_2_Final_Archive\lab_system\R52_CornerStabilityGuard\20260813_full_history\snapshot`
- 原始完整快照的八個來源已完成 SHA-256 清單並逐檔核對通過，共 23,856 個檔案、12,745,296,793 bytes（約 11.87 GiB）。2026-08-24 加入最終執行紀錄與精確清理腳本後，最終快照為 23,858 個檔案；實驗脈絡清單已重建並再次核對。
- D 槽保留 38 個關鍵證據檔案及一份說明，共 39 個檔案；來源與保留副本的 SHA-256 全部一致。
- R95 完成 48/48 且必要輸出核對通過後，已於 2026-08-24 精確移除七個列明的大型 D 槽來源：23,797 個檔案、12,548,851,895 bytes 的表面容量，實際回收 10,125,979,648 bytes（約 9.431 GiB）。
- 刪除前後八份 H 槽清單皆為 PASS；R52 實驗說明、報告、程式、測試、精簡保留包、執行紀錄與恢復方法均已同步到同一份 H 槽快照。

## D 槽保留內容

`results/archive_retained_20260813/` 保留 38 個關鍵證據檔案及一份說明：

- 4000 組正式資料與 700 組驗證資料的兩份 manifest；
- 正式 100 輪訓練日誌、驗證日誌、曲線、輸入與第 100 輪代表影像；
- `latest`、`best_tradeoff`、`best_detail_guarded` 三個代表模型；
- smoke 訓練的精簡日誌與代表影像；
- 真實角點驗證的完整表格、JSON 與代表圖。

README、MANIFEST、正式報告、腳本、測試與 gate 結果仍留在原 R52 實驗資料夾。

## H 槽逐檔清單

- `H:\GMM_2_Final_Archive\manifests\Lab_R52_training_data_20260813.csv`
- `H:\GMM_2_Final_Archive\manifests\Lab_R52_run_formal_20260813.csv`
- `H:\GMM_2_Final_Archive\manifests\Lab_R52_run_smoke_20260813.csv`
- `H:\GMM_2_Final_Archive\manifests\Lab_R52_corner_validation_20260813.csv`
- `H:\GMM_2_Final_Archive\manifests\Lab_R52_reconstruction_outputs_20260813.csv`
- `H:\GMM_2_Final_Archive\manifests\Lab_R52_gmf_best_tradeoff_20260813.csv`
- `H:\GMM_2_Final_Archive\manifests\Lab_R52_gmf_latest_20260813.csv`
- `H:\GMM_2_Final_Archive\manifests\Lab_R52_experiment_context_20260813.csv`

## 恢復方式

1. 先讀本檔、`ARCHIVE_SCOPE_R52_20260813.json` 與 `ARCHIVE_DELETE_PLAN_R52_20260813.json`，確認要恢復的原相對位置。
2. 在 H 槽先用對應 SHA-256 清單核對快照。
3. 把快照中的目錄複製回 `Thesis_MOSR_Evidence/LabSystem_MOSR/` 下的原相對位置，不要改名或合併到其他實驗。
4. 對恢復後的 D 槽目錄再使用同一份清單逐檔核對。
5. 若要重跑 2026-06-17 的資料風格稽核，必須先恢復 R52 資料包，因歷史輸出保留的是原絕對路徑。
6. 恢復後執行 R52 測試，再開始重建或分析。

R52 的正式訓練起點是 R51 mixed-PSF `best_tradeoff`；R51 不包含在本次封存範圍內。
