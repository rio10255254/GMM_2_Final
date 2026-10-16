# R87 合成資料清理：指令被工具拒絕

日期：2026-09-27

使用者要求直接執行刪除指令。本次對已完成、未升級的 R87 正式合成訓練影像陣列提出原生 PowerShell Remove-Item 指令；在程序建立前收到 blocked by policy。沒有檔案被刪除，也沒有改用其他方式繞過拒絕。

刪除前已重新逐檔核對 5,152 個 D/H 對應檔案，SHA-256 全部一致；當時沒有目前程序使用 R87。正式陣列與 smoke 陣列在拒絕後都仍留在 D，H 的完整 5,588 檔封存仍可用。刪除對象的清單在 H:/GMM_2_Final_Archive/operation_logs/R87_TileNativeScratchGeneralization_20260926/R87_dataset_thinning_candidate.json；本次實際拒絕及可用空間見同區 R87_cleanup_blocked_20260927.json。

目前對話權限是完整存取、approval_policy=never。此前同類移除在使用者切換「Ask for approval」並正式核准後曾成功；若要我繼續精簡，需讓下一輪採用可人工核准的權限設定。這不是重新索取檔案清理的授權，而是取得執行工具的正式放行。無論權限設定如何，仍須逐來源核對與保留正式成果。
