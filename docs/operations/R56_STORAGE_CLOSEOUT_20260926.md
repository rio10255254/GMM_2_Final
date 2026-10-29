# R56 歷史封存與待清理範圍

## 2026-09-26 最新狀態：封存與 D 槽清理完成

4 個已核對的歷史目錄已透過使用者正式核准，以原生 PowerShell 移除。
H 槽完整歷史 39,499 檔在移除後再次逐檔核對，全部一致。
D 槽保留內容 23 檔及 62 個原成果／程式／驗證檔再次核對通過。
正式訓練成果及原報告留在原位置；研究判決沒有改變。
兩批合計的當下 D 可用空間增加約 25.6136 GiB，清理完成時約 376.935 GiB。
此為兩批合計量測，沒有單獨歸算每輪回收量。其他訓練持續執行，檔案標示容量與真正占用不同。

恢復時由 H 的 payload 按 LabSystem 相對路徑複製回原位置，再按 source_manifest.csv 核對。
要重做歷史訓練，需先恢復資料，或在啟動程式明確指定封存資料位置。
完整副本：H:\GMM_2_Final_Archive\lab_system\R56_LabelCoreRepairTraining\20260926_full_history
本次實際移除與核對：docs/operations/storage_execution_20260926/native_cleanup_execution.json、post_cleanup_verification.json。

## 先前封存與拒絕紀錄（歷史狀態）

日期：2026-09-26

## 已完成

R56 是已完成但未採用的標籤修復實驗。本次只調整存放安排，沒有更改研究結論。

完整 H 副本共 39,499 檔、16.7828 GiB，來源及副本內容逐檔一致，複製期間來源未變。保存位置：H:\GMM_2_Final_Archive\lab_system\R56_LabelCoreRepairTraining\20260926_full_history。

D 槽保留原正式報告、程式、完整 50 輪正式訓練成果與角點驗證。另留 23 個資料清單、設定與代表影像，合計 52.120 MiB，內容再次核對通過。原正式訓練成果 38 檔再次核對通過。

原啟動程式使用 H 封存的資料通過只讀啟動檢查，讀到 6,000 組訓練配對；未啟動訓練。當前 C 槽 R61 訓練與本批來源無交集。

## 尚未完成

精確待清理為 4 個目錄、15.8983 GiB；扣除新增 D 保留內容，預計可減少約 15.8474 GiB 的檔案標示容量。實際磁碟回收量須在移除後另量測。

目前所有待清理原件仍在 D。本次實際回收 0 bytes。前批 R53 的原生移除命令被執行工具拒絕，本批未重試同類移除或繞過限制。[拒絕問題核對紀錄](STORAGE_TOOL_POLICY_DIAGNOSIS_20260926.md)

[精確待清理清單](R56_MANUAL_CLEANUP_PATHS_20260926.txt)

## 恢復與查找

從 H 的 payload 按 LabSystem 相對路徑複製回 D 原位置，再按 source_manifest.csv 核對。資料清單與重做方法在原 R56 實驗目錄及 results/archive_retained_20260926。完整清理與保留紀錄在 H:\GMM_2_Final_Archive\operation_logs\Storage_Migration_20260926/R56_cleanup_plan.json；核對收尾在 R56_closeout.json。
