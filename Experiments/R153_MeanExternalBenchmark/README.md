# MOSR mean aggregation and external benchmark

## 最新完成資料（2026-10-07）

十種可執行方法的完整驗證與論文資料已核對完成：各930張、8370讀值、30有效趟、零失敗；150次同條件效率與162組完整掃描配對區間。請用[完整交接文件](reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)、[修改指南](reports/FINAL_BENCHMARK_THESIS_HANDOFF/PAPER_UPDATE_GUIDE.md)及[圖表數據包](reports/FINAL_BENCHMARK_THESIS_HANDOFF.zip)。九方法舊包保持原樣，本次只補SwinIR；原論文／模型／既有量測／尺度／PI／方向未改。另兩官方後端阻礙明列，不冒充完成。監看在交付後結束。

獨立交付核對可執行 scripts/verify_final_delivery.py；它不進行GPU重建或重新擬合。機器核對與圖表審查在 results/full_benchmark/delivery_verified.json；主紀錄 BENCHMARK_RESULTS.md、THESIS_UPDATE_MAP.md 均指向最新十方法。

## 下列為歷史執行紀錄

先前等待、暫停與預估時間是歷史，當前完成狀態以上節與最新交接文件為準。

Profile: self-contained benchmark tools; immutable shared TIFF training data and saved real readouts are referenced without copying bulk payloads.

Task: reproduce the published componentwise-median result, make the arithmetic mean of nine displacement vectors primary, and compare RAW, Wiener, U-Net, EDSR-x1, RDN-x1, RCAN-x1, NAFNet, SwinIR, Restormer, MambaIRv2, USRNet-x1 and MOSR fairly.

Completion requires all saved measurements to be verified; all requested mean/median metrics and scan-level paired intervals; official-model source identities and honest blocked reasons; completed eligible from-scratch trainings; 930-frame reconstruction/readout for each completed comparator; fresh matched runtime; complete reports and THESIS_UPDATE_MAP.md. No claim of completion while training or real readout remains unfinished.

No MOSR architecture/weights, original thesis, existing circle fits, scale, direction, PI, or source results are modified. Public paper material uses MOSR, never internal development names. RAW is the original-image baseline. New model settings/checkpoint selection use only synthetic data. Full scans are resampling units. No unfavorable result is discarded.

Branch: sandbox/r153-mean-external-benchmark; inherited current research checkout f0183af6e03954804d0ad82b2687149623e94700 to preserve existing uncommitted work and current evidence paths. main remains unchanged. Local tracking only; no remote publication requested.

Shared data: Deliverables/R152_Standalone_ImageFiles_20261004/data. Model/measurement lineage is recorded in config/source_lock.json. Requested public reports are reports/MEAN_MEDIAN_RESULTS.md, reports/BENCHMARK_RESULTS.md and reports/THESIS_UPDATE_MAP.md. The latter two now exist: the update map records confirmed mean-analysis changes, while the benchmark report explicitly marks unfinished real comparisons. After monitoring, run scripts/write_benchmark_progress.py to refresh verified training and synthetic results without GPU inference.

Storage: D retains active code, fixed protocol, weights, reconstructions, readouts and complete reports; 160 GiB new-output budget, stop before D free falls below 50 GiB. No cleanup of existing results. H is a future verified archive destination, not an implicit move authorization.

Fresh efficiency runner: scripts/benchmark_runtime.py --method <public-method-name>, one new process per method after the training queue exits. It verifies the same three source frames (0, 465, 929), uses FP32/batch=1, two warmups and five timed forwards per frame, and records allocated/reserved peaks before output checks. --inspect checks frame identities without GPU execution. Both inspection and refusal during active training were exercised; actual GPU efficiency measurements are still pending. Do not substitute these preparation checks for measured timings.

Latest authorized duration: config/TIME_BUDGET_OVERRIDE.json supersedes the32-epoch limit for the four not-yet-started models (cap8). Existing completed32-epoch results remain; RDN finalizes saved best after14 complete epochs plus128 saved partial updates. This is explicitly an unequal-duration, shorter-training comparison. Do not restore32 epochs without user authorization.

Latest monitoring schedule: check near estimated model completion plus20-minute buffer, not fixed15-minute polling. Next check2026-10-06 02:15 Asia/Taipei; recalculate/reschedule for whichever model is then active. Queue transitions remain immediate and independent of heartbeat wakeups.

Completed first-part thesis handoff: [standalone mean-analysis document](reports/MOSR_MEAN_THESIS_HANDOFF_20261005/MOSR_MEAN_THESIS_HANDOFF.md), [verified complete ZIP](reports/MOSR_MEAN_THESIS_HANDOFF_20261005.zip). Contains12 CSV tables, grayscale replacement Figures6-12/13/14, full30-scan and30-position summaries, mean/median sensitivity, first6/last24 sensitivity, explicit long-distance limitations, unchanged geometry, and portable saved-center/PI recalculation. Independent7200-row/36-interval verification and package hashes passed. This mean-only delivery is complete; external-model benchmark remains incomplete. Rebuild via scripts/build_mean_thesis_handoff.py.

2026-10-05 evening user priority: pause training and releaseGPU to validate completed models now. Restormer saved atstep896, exact backup in runs/launcher_logs/validation_training_pause. VALIDATION_PRIORITY.json blocks training restore while scripts/validate_available_queue.py is active. Status: runs/validation_logs/status.json. Seven-method isolated FP32/batch1 efficiency is complete (105 samples); Wiener real930/readout8370 passed without failures. EDSR, NAFNet, RDN, RCAN real930 run sequentially, with fixed-reader CPU processing. No RAW/MOSR refits or full MOSR re-inference. Final result audit generates AVAILABLE_MODELS_REAL_RESULTS.md and AVAILABLE_MODELS_STAGE_COMPLETE/REPORT.md, removes validation priority and restores the saved8-epoch training queue. If validation fails, preserve priority and investigate; do not start training alongside validation. Next adaptive check2026-10-06 03:45 Asia/Taipei.

[Completed efficiency report](reports/AVAILABLE_MODELS_EFFICIENCY.md) and [current paper handoff](reports/AVAILABLE_MODELS_STAGE_PROGRESS/REPORT.md) may be used now; the latter explicitly includes only RAW/Wiener/MOSR real results while neural real results remain pending. Refresh partial results with scripts/summarize_available_real.py --partial then scripts/build_available_handoff.py --partial. This does not modify weights or inference settings.

2026-10-06 complete available stage verified: AVAILABLE_MODELS_STAGE_COMPLETE/REPORT.md and ZIP, all7 methods930 images/8370 readouts/30 validscans without failures,108 paired intervals and105 runtime samples. No new RAW/MOSR fits or fullMOSR inference. Original sources and complete ZIP hashes verified; figures inspected. Restormer restored and progressing with8-epoch cap; next adaptive check2026-10-06 07:45Taipei. This stage is complete; remaining external methods/fullbenchmark are not.

2026-10-06 11:35: USRNet-x1 completed8 epochs,selected8,128-scene test and checkpoint verified. SwinIR is last training,max8. Final validation already waiting via scripts/run_final_validation.py --watch (status runs/final_validation_logs/status.json): require all7 training receipts and no training manager/worker beforeGPU, then only new Restormer/USRNet/SwinIR runtime+real930+fixedreadout. Prior seven results reused. Final reporting routes (--final) prepared; final GPU execution still pending, not marked complete. Next adaptive check2026-10-07 03:00Taipei based on actual12.8s/update and measured initial validation duration+20min buffer. No source recipes or earlier delivered packets changed.

LATEST USER SCOPE: SwinIRexplicitly paused atstep256, noauto resume; USER_STOP_REQUESTED remains. Completed-onlynine-method comparison nowuses scripts/run_final_validation.py --completed-only --watch (status runs/completed_validation_logs/status.json). Only newRestormer/USRNet runtime+real930; originalseven reused. Finaltargets COMPLETED_MODELS_RESULTS.md, COMPLETED_MODELS_EFFICIENCY.md, COMPLETED_MODELS_THESIS_HANDOFF/REPORT.md andZIP; fullaudit results/completed_models. Stopmonitor aftercurrent scopedelivery, do not reviveoldSwin watcher. NextcheckOct6 15:00Taipei.

DELIVERED COMPLETE USER SCOPE (2026-10-06): nine completed methods930/8370/30validscans each,zero failures,144paired intervals,135efficiency samples; REPORT.md,PAPER_UPDATE_GUIDE.md,source identities,allCSV,grayscale figures,original ROI pixels andZIP in reports/COMPLETED_MODELS_THESIS_HANDOFF. Audit and independent checks passed; original sources unchanged. SwinIRpausedstep256 retained, USER_STOP_REQUESTED remains, noautomatic resume. AutomationmosrPAUSED afterdelivery. This completes currentnine-method paper scope; untrainedpausedSwin andtwoofficial backend blockers are not mislabeled complete.


## 2026-10-06 九方法交付後恢復 SwinIR

使用者直接要求續訓，SwinIR 從原 step256 保存點繼續，總上限仍8輪，資料與訓練設定不變。已交付九方法的全部結果、135次效率與論文資料包保留；只新增 SwinIR 的15次效率、930張重建與8370讀值，再另行彙整十方法成果。監看恢復，原完成後驗證主管已接續等待訓練釋放GPU。詳細授權與來源核對見 config/USER_RESUME_20261006.json。


## 2026-10-07 最新已核對進度

SwinIR已完成8輪／4096次更新，合成驗證選第8輪EMA；完整128場景合成測試、來源與保存權重已核對。七個可執行外部模型皆完成訓練。同GPU／FP32／batch=1的SwinIR15次效率已完成，使用原生整張；現自動執行930張原生重建及8370固定讀值。巡檢成功230張且零重建失敗。現有九方法930張及135次效率／論文資料包全部直接重用，本次只新增SwinIR；十方法最終數據／灰階圖與完整交接須在全部930與30趟核對後才發布。下一次檢查按目前28.13秒／張估計，安排2026-10-07T14:15:00+08:00，包含後續讀值／報告及20分鐘緩衝，並非保證。
