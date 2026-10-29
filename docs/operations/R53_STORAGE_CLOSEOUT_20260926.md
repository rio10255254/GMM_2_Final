# Lab R53 封存與 D 槽清理狀態

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
本次實際移除與核對：docs/operations/storage_execution_20260926/native_cleanup_execution.json、post_cleanup_verification.json。

## 先前封存與拒絕紀錄（歷史狀態）

日期：2026-09-26  
狀態：完整 H 副本、D 保留包及封存資料讀取檢查全部通過；D 移除被執行工具拒絕。

## 已完成

使用者明確授權操作與目前程序無關的檔案。R53 的 19 個精確來源與目前 C 槽 R61 訓練、R147 nuisance 核對的實際資料位置沒有交集；已保存逐來源放行證據。

H 完整副本位置：H:/GMM_2_Final_Archive/lab_system/R53_RealisticDatasetCalibration/20260926_full_history

- 39,661 個檔案，20,085,159,214 bytes（18.7058 GiB）。
- 檔案清單、大小及逐檔 SHA-256 核對全部通過；複製期間 D 原始來源未變。
- 完整保存資料、12 次執行紀錄、正式與失敗證據、重建、GMF 影像及角點驗證。
- 原始啟動程式用 H 封存資料通過 dry-run，能讀到 6,000 組訓練配對；沒有啟動訓練。
- dry-run 後再次確認 H 的完整檔案集合、大小及時間均符合封存清單。

## D 槽保留

R53 完整實驗說明、程式、正式報告、完整 batch16 正式訓練 run、角點驗證資料及共享驗證程式留在原位置。其餘失敗 run 的設定、日誌與代表影像，以及資料 manifest，另保存到：

Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R53_RealisticDatasetCalibration/results/archive_retained_20260926

這個保留包有 121 個檔案、134,430,502 bytes（128.203 MiB）；每個檔案與 H 原件 SHA-256 相同，最後複核再次通過。原位置新增 ARCHIVE_POINTER_R53_20260926.md，說明恢復相對路徑。

## 未完成的移除

精確清理清單有 15 個資料夾、39,555 個檔案、18,429,859,138 bytes（17.1641 GiB）。扣除新增 D 保留包後，淨檔案標示容量約 17.038 GiB；這不是已量到的回收量。

本次先以原生 PowerShell 對已核對的 R53 訓練資料根目錄嘗試移除。自動命令審查拒絕啟動命令，回覆只有「blocked by policy」。沒有改用其他移除或移動機制規避拒絕。15 個待清理來源全部仍存在，D 槽本次實際回收 0 bytes。

若由使用者手動執行已授權清理，只移除 [15 個精確資料夾](R53_MANUAL_CLEANUP_PATHS_20260926.txt)。完整 batch16 正式 run、實驗報告和角點驗證不在該清單；不要改成上層 Training_Data、Traing_Progress 或整個 LabSystem。

## 記錄與續點

操作資料位置：H:/GMM_2_Final_Archive/operation_logs/Storage_Migration_20260926

- scoped_authorization_R53.json：使用者授權與目前程序來源不重疊的證據。
- R53_cleanup_plan.json：精確移除範圍和 D 保留包。
- R53_retained_manifest.csv：保留檔案 SHA-256。
- R53_archive_dry_run.log：H 資料能由原啟動程式讀取的結果。
- R53_closeout.json：副本、保留包、移除拒絕與 D/H 空間最後觀察。
- H 完整快照根目錄的 verification.json、source_manifest.csv、copy.log：來源與副本核對。

R56 仍只完成前置來源清單，沒有開始大型複製。依原分批次序，R53 的 D 精簡和復核完成後才進下一批。
