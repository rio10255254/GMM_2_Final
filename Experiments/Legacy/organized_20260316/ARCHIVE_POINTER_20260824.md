# organized_20260316 歷史封存與恢復入口

本批包含 Round23–31、Round32 歷史載荷、外部比較鏈與 TTA 支線。完整歷史保存於 `H:\GMM_2_Final_Archive\legacy\organized_20260316\20260824_full_history\snapshot`。快照共 5,073 個檔案、17,528,038,742 bytes，刪除前後逐檔核對均為 PASS。

D 槽永久保留所有 `selected`、`pending`、README、MANIFEST、postmortem、正式比較報告、GMF 原始分數與分析。Round30 前任正式基準與 Round31 的正式歷史入口特別保護。2026-08-24 已移除 25 個列明的 `archive`、逐張重建與比較載荷目錄，共 4,701 個檔案、17,291,097,265 bytes；D 槽薄化後保留 372 個檔案、236,941,477 bytes。

恢復時先核對 `H:\GMM_2_Final_Archive\manifests\organized_20260316_20260824_full.csv`，再把所需相對路徑複製回本資料夾並使用同一份清單核對。
