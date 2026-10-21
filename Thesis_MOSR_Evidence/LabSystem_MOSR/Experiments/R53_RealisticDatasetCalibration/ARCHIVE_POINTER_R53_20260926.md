# R53 完整歷史封存入口

## 2026-09-26 最新狀態：封存與 D 槽清理完成

15 個已核對的歷史目錄已透過使用者正式核准，以原生 PowerShell 移除。
H 槽完整歷史 39,661 檔在移除後再次逐檔核對，全部一致。
D 槽保留內容 121 檔及 104 個原成果／程式／驗證檔再次核對通過。
正式訓練成果及原報告留在原位置；研究判決沒有改變。
兩批合計的當下 D 可用空間增加約 25.6136 GiB，清理完成時約 376.935 GiB。
此為兩批合計量測，沒有單獨歸算每輪回收量。其他訓練持續執行，檔案標示容量與真正占用不同。

恢復時由 H 的 payload 按 LabSystem 相對路徑複製回原位置，再按 source_manifest.csv 核對。
要重做歷史訓練，需先恢復資料，或在啟動程式明確指定封存資料位置。
完整副本：H:\GMM_2_Final_Archive\lab_system\R53_RealisticDatasetCalibration\20260926_full_history
本次實際移除與核對：D:/GMM_2_Final/docs/operations/storage_execution_20260926/native_cleanup_execution.json、post_cleanup_verification.json。
