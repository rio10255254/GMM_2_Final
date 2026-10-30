# Lab R46 歷史封存與恢復入口

Lab R46 是完成但未升級的第一個角點微調輪次。完整資料、訓練與重建歷史保存於 `H:\GMM_2_Final_Archive\lab_system\R46_CornerAwareFineTune\20260824_full_history\snapshot`；各來源清單位於 `H:\GMM_2_Final_Archive\manifests\Lab_R46_*_20260824.csv`。11 個來源共 3,710 個檔案、2,963,223,914 bytes，刪除前後逐檔核對均為 PASS。

D 槽保留 README、MANIFEST、正式報告、程式、測試、正式訓練日誌，以及 `results/archive_retained_20260824` 中的 32 個資料清單、代表模型與角點驗證檔。10 個大型來源共 3,664 個檔案、2,793,698,096 logical bytes 已移除。恢復時先核對對應清單，再把所需相對路徑複製回 LabSystem 根目錄。
