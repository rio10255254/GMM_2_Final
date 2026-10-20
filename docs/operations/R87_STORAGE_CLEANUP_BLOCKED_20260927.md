# R87 合成資料清理：指令被工具拒絕

日期：2026-09-27

使用者要求直接執行刪除指令。本次對已完成、未升級的 R87 正式合成訓練影像陣列提出原生 PowerShell Remove-Item 指令；在程序建立前收到 blocked by policy。沒有檔案被刪除，也沒有改用其他方式繞過拒絕。

刪除前已重新逐檔核對 5,152 個 D/H 對應檔案，SHA-256 全部一致；當時沒有目前程序使用 R87。正式陣列與 smoke 陣列在拒絕後都仍留在 D，H 的完整 5,588 檔封存仍可用。刪除對象的清單在 H:/GMM_2_Final_Archive/operation_logs/R87_TileNativeScratchGeneralization_20260926/R87_dataset_thinning_candidate.json；本次實際拒絕及可用空間見同區 R87_cleanup_blocked_20260927.json。

目前對話權限是完整存取、approval_policy=never。此前同類移除在使用者切換「Ask for approval」並正式核准後曾成功；若要我繼續精簡，需讓下一輪採用可人工核准的權限設定。這不是重新索取檔案清理的授權，而是取得執行工具的正式放行。無論權限設定如何，仍須逐來源核對與保留正式成果。

## 2026-10-20：依使用者要求維持原模式，單次刪除成功

使用者明確要求實際試一次已完整備份的 R87 副本，禁止切換成人工核准，保護正在訓練及論文需要的資料。已重新確認 R87 正式 100 輪與 smoke 皆完成，沒有程序使用它；目前 H 槽 R152 v8 的模型、資料與輸出留在其獨立包，R152/R153 論文設定也沒有引用這兩個 R87 陣列目錄。

刪除前對兩個目錄的 D、H 不可變封存與 H 獨立工作副本共三份資料重新完整讀取核對，5,152 檔全部相同。以原模式 `never / danger-full-access` 只送出一次原生 PowerShell `Remove-Item -LiteralPath $targets -Recurse -ErrorAction Stop`，沒有使用 `-Force`、權限提升、人工核准或替代刪除工具。這次指令成功返回，兩個 D 實體陣列目錄皆已移除。不能將本次成功直接歸因於撤回專案設定，先前內部拒絕原因仍未確定。

移除合計 12,155,752,448 bytes；實測 D 空間增加 12,176,003,072 bytes（11.3398 GiB）。原 D 入口改接到先前已完整核對的 H 工作副本，原生程式正式／smoke 的首、中、尾讀取全部一致。原保留 438 檔內容通過核對，模型、科學報告、原照片及論文資料未清理；H 槽訓練程序刪除後仍在執行。20x/5x 與其他批次沒有嘗試刪除。

詳見 [R87 最新封存入口](../../Experiments/R87_TileNativeScratchGeneralization/ARCHIVE_POINTER_R87_20260926.md)。本次原始指令與完整收據在 `H:/GMM_2_Final_Archive/operation_logs/R87_Cleanup_Trial_20261020/`。上文保留 9 月 27 日受阻經過，不再代表目前這批副本仍未移除。
