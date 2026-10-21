# R130-Clean 執行入口

- 規格：config/USER_SPECIFICATION.md，原文保留。
- 配置：config_r130_clean.yaml，正式開始前固定。
- 程式：model_r130_clean.py、dataset_r130_clean.py、losses_r130_clean.py、train_r130_clean.py、infer_r130_clean.py。
- 流程：scripts/launch_r130.py、START_R130.cmd。
- 狀態：runs/pipeline_status.json、runs/formal_8192/status.json。
- 初始來源：scratch，PSF off，不載入歷史权重。
- 自查：results/preflight.json；32步sanity獨立，正式不承接其參數。
- 資料：data/manifest.json，768母場景的原值白名單副本。
- 評估：evaluation/中的固定Raw追蹤、既有量測核心、兩種SEM方向與基準輸出。
- 新重建：results/reconstruction → H:/GMM_2_Final_Archive/active_runs/R130_Clean_20260920/reconstruction。
- 完成：results/complete.json及reports/R130_CLEAN_RESULTS.md；未生成前不得稱正式驗收完成。
- 容量：D新增預估4GiB，H活動資料預估30GiB，已登錄儲存清單；不刪既有資料。
