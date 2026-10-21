# R44 歷史封存與恢復入口

R44A–R44H 已完成，研究上有價值但沒有可直接升級的模型。完整實驗保存於 `H:\GMM_2_Final_Archive\experiments\R44_UniversalBoundaryMotionFidelity\20260824_full_history\snapshot`，清單為 `H:\GMM_2_Final_Archive\manifests\R44_UniversalBoundaryMotionFidelity_20260824_full.csv`。快照共 21,414 個檔案、9,336,509,252 bytes，刪除前後逐檔核對均為 PASS。

D 槽最終保留 324 個檔案、810,483,355 bytes：README、MANIFEST、全部報告、程式、測試、診斷表、摘要、代表圖、R44H 小型結果，以及九個 R44B/R44C/R44E 代表模型；21,062 個逐張 motion/ring 重建檔、9,121,747,374 bytes 已移除。原始訓練 run 另由完整 `Traing_Progress` 快照保存。恢復時先核對清單，再按原相對路徑複製回來。
