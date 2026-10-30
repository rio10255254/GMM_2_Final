# 主專案共享訓練歷史封存與恢復入口

2026-08-24 的完整 `Traing_Progress` 時間點快照保存於 `H:\GMM_2_Final_Archive\main_training_history\20260824_full_snapshot\snapshot`，完整清單為 `H:\GMM_2_Final_Archive\manifests\Traing_Progress_20260824_full.csv`。快照共 3,751 個檔案、56,605,822,481 bytes，D 精簡前後逐檔核對均為 PASS。

本快照涵蓋舊日期批次、正式與研究訓練 run、失敗探針、模型權重、曲線與中間輸出。2026-08-24 已依精確清單移除 61 個已結案、失敗、探針或消融 run，共 1,305 個檔案、24,064,796,954 logical bytes；D 槽實測回收 22.4152 GiB。COMBO、R33、R38v2、R39/R40 採用模型與未能可靠對應的舊主線歷史不在刪除範圍。

R42、R44、R46 報告需要的代表模型已另存到各自實驗的 `results/archive_retained_20260824/`。D 槽目前保留 2,446 個訓練歷史檔、32,541,025,527 bytes。恢復任何 run 時，先核對完整清單，再把該資料夾按原名稱複製回本目錄。
