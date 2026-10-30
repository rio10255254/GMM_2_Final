# organized_20260313 歷史封存與恢復入口

本批包含 Round16–19 與舊根狀態橋接。完整歷史保存於 `H:\GMM_2_Final_Archive\legacy\organized_20260313\20260824_full_history\snapshot`。快照共 3,707 個檔案、11,976,304,694 bytes，刪除前後逐檔核對均為 PASS。

D 槽永久保留每輪 `selected`、`pending`、README、MANIFEST、正式報告及 `root_status_legacy`。2026-08-24 已移除 7 個列明的 `archive` 與重複外部驗證目錄，共 3,487 個檔案、11,186,501,220 bytes；D 槽薄化後保留 220 個檔案、789,803,474 bytes。

恢復時先核對 `H:\GMM_2_Final_Archive\manifests\organized_20260313_20260824_full.csv`，再把所需相對路徑複製回本資料夾並使用同一份清單核對。
