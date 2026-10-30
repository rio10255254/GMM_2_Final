# Lab R47 歷史封存與恢復入口

Lab R47 完成 200 輪訓練但未通過真實角點驗證，不升級。完整資料、訓練與重建歷史保存於 `H:\GMM_2_Final_Archive\lab_system\R47_RealisticBoundaryGeneralization\20260824_full_history\snapshot`；各來源清單位於 `H:\GMM_2_Final_Archive\manifests\Lab_R47_*_20260824.csv`。10 個來源共 9,987 個檔案、6,794,448,117 bytes，刪除前後逐檔核對均為 PASS。

D 槽保留 README、MANIFEST、正式報告、程式、測試、正式訓練日誌，以及 `results/archive_retained_20260824` 中的 35 個資料清單、代表模型與角點驗證檔。9 個大型來源共 9,935 個檔案、6,607,020,616 logical bytes 已移除。恢復時先核對對應清單，再把所需相對路徑複製回 LabSystem 根目錄。
