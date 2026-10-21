# R87保存核對及D副本清理受阻

本次重新完整核對兩個舊合成陣列目錄：正式5120檔、smoke32檔，D原件、H完整歷史副本及獨立H工作副本逐檔完全相同。原訓練資料讀取程式從H工作副本讀取2048個訓練範例，首／中／尾的來源、答案、位置與角色均與D相同；沒有新訓練。

資料、原模型、完整數值與方法已在GitHub保存，原未採用結論保持不變。準備移除這兩個D副本並保持舊讀取位置時，原生PowerShell指令在程序建立前被自動審查以blocked by policy拒絕；兩個D目錄仍完整存在。實際刪除0檔、回收0 bytes。

H完整歷史副本未更改；獨立工作副本位於H:/GMM_2_Final_Archive/compatibility_views/R87_TileNativeScratchGeneralization/20261016/data，供後續能正式放行時保持舊位置使用。完整路徑、內容核對與拒絕記錄見本次H槽操作紀錄。[總收尾](../../../docs/operations/GITHUB_PRESERVATION_CLOSEOUT_20261016.md)。
