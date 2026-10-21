# R46 歷史封存與恢復入口

R46 主場畫質提升，但三尺度 ring 與外部 GMF 均失敗，屬 research-only 且不可升級。完整實驗保存於 `H:\GMM_2_Final_Archive\experiments\R46_CornerAwareFineTune\20260824_full_history\snapshot`，清單為 `H:\GMM_2_Final_Archive\manifests\R46_CornerAwareFineTune_20260824_full.csv`。快照共 1,011 個檔案、1,790,053,182 bytes，刪除前後逐檔核對均為 PASS。

D 槽最終保留 86 個檔案、67,830,386 bytes：README、MANIFEST、正式報告、程式、ring guard、外部 GMF 原始分數、能力表、Rayleigh 診斷、訓練紀錄、代表圖與正式主 run 的代表模型；919 個 ring、shape 與 micro 逐張重建檔、1,774,776,122 bytes 已移除。原始訓練 run 另由完整 `Traing_Progress` 快照保存。恢復時先核對清單，再按原相對路徑複製回來。
