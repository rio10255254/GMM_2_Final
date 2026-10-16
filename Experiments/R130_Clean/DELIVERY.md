# R130-Clean 完整交付入口

本輪已完成規格要求的建構、scratch8192次訓練、生成驗證、930張原尺寸重建、8370輪廓量測、三方法比較、速度／記憶體檢查及獨立複核。

| 交付內容 | 位置 |
|---|---|
| 完整程式與操作方式 | README.md、START_R130.cmd |
| 固定設定與啟動身分 | runs/formal_8192/run_config.json |
| 凍結的程式／配置／資料清單身分 | config/source_lock.json |
| 最終模型與SHA256 | runs/formal_8192/checkpoints/step08192.pth、runs/formal_8192/latest_checkpoint.json |
| 參數量與8192次實際更新 | runs/formal_8192/training_complete.json、updates.jsonl |
| 訓練與開發曲線 | reports/figures/training_curves.png、runs/formal_8192/evaluations/ |
| 生成測試摘要 | runs/formal_8192/evaluations/test_08192.json |
| 930張原尺寸FP32重建及16bit顯示圖 | results/reconstruction/（連接H槽） |
| 位移、尺寸、輪廓、SEM完整表 | results/comparison/ |
| 整張與切塊速度及記憶體 | results/profile.json、results/profile_tiled_fresh.json |
| 訓練來源說明 | reports/TRAINING_PROVENANCE.md |
| 完整結果與取捨 | reports/R130_CLEAN_RESULTS.md |
| 獨立訓練與輸出核對 | results/independent_final_training_audit.json、results/independent_review/verification.json |
| 最後交付核對 | results/final_review_complete.json |

最終權重SHA256：559afeff214ff15e92ce910d7df7ead12994074b6173dabe9a7f21a8b40372cc。

沒有載入舊神經權重、舊optimizer或EMA，PSF OFF，沒有SEM／PI／真實影像訓練。光學feature分支未啟用。舊R129、舊R130_CleanV42Comparison與歷史結果保留，沒有自動抽換論文或正式基準。

目前正常完成後再次開START_R130.cmd只會指出結果位置，不重複覆寫。單張推論請用README中的infer_r130_clean.py指令，指定本輪最後權重；正式量測讀NPZ，不讀顯示用PNG。

全部重建實體位置：H:/GMM_2_Final_Archive/active_runs/R130_Clean_20260920/reconstruction。程式、資料、權重與小型報告留在D槽。既有原照片及校正參照的來源路徑與雜湊已明列；舊檔保護檢查只核對身分，不把它們當訓練輸入。
