# User clarification, 2026-10-05

The user clarified that external models should use ordinary training and epoch-based progress, with appropriate training duration rather than mechanically matching MOSR's two-stage update count. The user then explicitly chose: 各模型採一般訓練做法（建議）；固定相同資料與驗證規則.

This supersedes the initial request to train every external network with the five MOSR losses and the tentative fixed 16384/8192-update budgets. Formal external training has not begun before this change. The common five losses remain evaluation diagnostics only. No MOSR weights, original thesis, saved optical circle fits or PI/scales/directions are modified.

All external neural models start from scratch, use their ordinary author loss and optimizer settings, use independent image/clear pairs from the same fixed scene-disjoint TIFF bank, share the valid supervision region and synthetic validation protocol, and have actual epoch counts and validation-based selected weights recorded. No real images, PI or SEM enter training or selection.

## User-authorized shorter duration, 2026-10-05

User chose 約1天：各模型最多8輪，記錄為較短訓練的比較. Effective override: config/TIME_BUDGET_OVERRIDE.json. RCAN-x1, Restormer, USRNet-x1 and SwinIR cap at8 epochs. EDSR-x1/NAFNet completed32 epochs are preserved; RDN-x1 finalizes its saved synthetic best after14 complete epochs and128 saved partial updates. Actual unequal durations are reported. Original losses, optimizers, data, valid supervision region and synthetic-only selection remain fixed; full real930 verification still required. The original32-epoch protocol is retained as historical provenance. scripts/train_external.py dispatches the explicit short-budget entry; normal_training.py, model factory and data source are unchanged.

## Latest direct user steering, 2026-10-06

User explicitly pausesSwinIR and requests complete paper records for already-completed models now. COMPLETED_ONLY_SCOPE.json is authoritative: six completedexternal models plus RAW/Wiener/MOSR, nine methods; only Restormer/USRNet still need real930. SwinIRsaved atstep256 (half of firstepoch), no complete epoch/selected validated weight; excludedfrom comparison and keptpaused, no automatic resume. USER_STOP_REQUESTED protects this. Old final watcher stopped. Only completed-only validation remains authorized; once fullnine results/data/reports/map/figures audited and delivered, stop monitoring and preserve pause.


## 2026-10-06 九方法交付後，使用者直接授權續訓

使用者最新指示：「因為已完成所以你可以續訓了」。此指示解除先前 SwinIR 暫停，從已保存 step 256 接續，總上限仍為 8 輪；沿用相同資料、模型、一般訓練目標、最佳化與合成驗證選權重規則。已交付的九方法資料包維持原樣。訓練完成且 GPU 釋放後，只補 SwinIR 的效率與完整 930 張實拍／8370 讀值，再用既有九方法資料彙整十方法成果。恢復同一 mosr 監看，按實際速度估計完成時間加約 20 分鐘緩衝安排，不固定每 15 分鐘巡檢。詳見 config/USER_RESUME_20261006.json；早先暫停及九方法範圍紀錄保留為歷史。
