# R42 歷史封存與恢復入口

R42 證明顯微邊界能力，但外部 GMF 退步過大，屬研究用途且不可作量測替代。完整實驗保存於 `H:\GMM_2_Final_Archive\experiments\R42_MicroscopyBoundaryFidelity\20260824_full_history\snapshot`，清單為 `H:\GMM_2_Final_Archive\manifests\R42_MicroscopyBoundaryFidelity_20260824_full.csv`。快照共 4,653 個檔案、7,401,011,942 bytes，刪除前後逐檔核對均為 PASS。

D 槽最終保留 360 個檔案、254,507,965 bytes：README、MANIFEST、正式報告、程式、測試、ring guard、訓練紀錄、24 個 GMF/邊界核心檔，以及三個報告所需代表模型；4,278 個完整權重掃描與逐張重建檔、7,324,600,458 bytes 已移除。原始訓練 run 另由完整 `Traing_Progress` 快照保存。恢復時先核對清單，再按原相對路徑複製回來。
