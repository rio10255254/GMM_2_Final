# R32 歷史封存與恢復入口

R32 已由正式外部比較證實失敗，不是可採用模型。完整實驗保存於 `H:\GMM_2_Final_Archive\experiments\R32Sandbox\20260824_full_history\snapshot`，清單為 `H:\GMM_2_Final_Archive\manifests\R32Sandbox_20260824_full.csv`。快照共 356 個檔案、1,121,207,740 bytes，刪除前後逐檔核對均為 PASS。

D 槽保留 64 個正式失敗報告、README、MANIFEST、程式與治理檔，共 1,633,253 bytes；292 個大型訓練與逐張比較檔、1,119,574,487 bytes 已移除。恢復時先核對清單，再按原相對路徑複製回來。
