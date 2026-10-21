# R41 Manifest

## 實驗身份

- Round：R41
- 名稱：環形知識蒸餾
- 目錄：`Experiments/R41_RingDistillation/`
- 分支：`sandbox/r41`
- 主要目標：用顯式 teacher anchoring 保住 R40 的 microscopy capacity，同時把 ring 行為拉回 COMBO 附近。

## 主要檔案

| 類型 | 位置 | 用途 |
|---|---|---|
| 資料產生 | `scripts/r41_data.py` | 700 ring / 250 shape / 250 microscopy replay 包 builder |
| 訓練啟動 | `scripts/launch_r41.py` | R41 訓練啟動器 |
| KD 模組 | `scripts/r41_kd_module.py` | role-gated KD 助手，含單元測試 |
| 微觀重建 | `scripts/run_r41_micro_recon.py` | 跑 unseen microscopy 重建 |
| 微觀指標 | `scripts/r41_micro_metrics.py` | 重建指標彙總 |
| Ring guard | `scripts/run_r41_ring_guard.py` | local 720-angle ring guard |
| 權重 sweep | `scripts/run_r41_weight_sweep.py` | COMBO ↔ R41 平均 checkpoint sweep |
| 外部比較 | `scripts/r41_external_compare.py` | 外部 GMF verdict |
| 報告 | `reports/R41_RESULTS.md` | R41 canonical 結果紀錄 |
| 外部紀錄 | `reports/R41_EXTERNAL_COMPARE.md` | 外部 GMF 結果（目前未送） |

## 目前狀態

- 設施已建立：資料 builder、launcher、KD module、評估器、權重 sweep、外部比較器。
- 正式訓練已完成：`r41_kd_from_a045` 30 epoch。
- 微觀驗證已完成：direct best PSNR `29.4556`、HF retention `0.7241`。
- Local ring guard 已完成：direct best 三尺度全退步（8px `0.1628`、0.8px `0.1652`、0.08px `0.1543` vs COMBO `0.1389` / `0.1509` / `0.1185`）。
- 權重 sweep 已完成：alpha `0.10`–`0.40` 沒有共同通過點，高 alpha `0.45` / `0.50` 微觀過但 ring 不過。
- 結論：研究成功保住 capacity 但無可升級候選；外部 GMF 未送測。

## 資料

- 訓練包：`Training_Data/r41_ring_distillation/r41_ring_recover_train`
- 驗證包：`Training_Data/r41_ring_distillation/micro_val_unseen`

## 主要產物

> Storage note (2026-08-01): 完整歷史已逐檔核對封存。D 槽保留 canonical 報告、程式、測試、數字摘要與代表模型；完整位置、清單及恢復方式見 `ARCHIVE_POINTER.md`。

| 類型 | 位置 | 說明 |
|---|---|---|
| 訓練 run | H 槽完整封存；見 `ARCHIVE_POINTER.md` | 30 epoch 正式訓練 |
| Direct best checkpoint | D 槽 `selected_checkpoint/best_tradeoff.pth.tar`；完整訓練亦在 H 槽 | R41 研究候選，未升級 |
| 微觀重建 | H 槽 `experiment/results/micro_recon/r41_kd_from_a045_best/` | held-out microscopy 完整重建 |
| 微觀彙總 | `results/micro_recon/r41_kd_from_a045_best_summary.json` | 微觀指標 JSON |
| Ring 重建 | H 槽 `experiment/results/ring_recon/r41_kd_from_a045_best/` | local 三尺度 ring 完整重建 |
| Ring guard 彙總 | `results/ring_guard/r41_kd_from_a045_best_ring_guard_summary.json` | ring guard 結果 |
| 正式權重 sweep | D 槽保留摘要；完整內容在 H 槽 | alpha `0.10`–`0.40` |
| 正式 sweep 摘要 | `results/weight_sweep/sweep_summary.md` / `sweep_summary.json` | sweep 結論 |
| 高 alpha 診斷 sweep | D 槽保留摘要；完整內容在 H 槽 | alpha `0.45` / `0.50` |
| 高 alpha 診斷摘要 | `results/weight_sweep_ext_high_alpha/sweep_summary.md` / `.json` | 診斷結論 |
| 外部 GMF drop folder | `results/external_gmf/pitch{8px,0p8px,0p08px}` | 預留位置（目前未送） |

## 注意事項

- R41 是研究路線，沒有正式升級候選；ring guard 是淘汰線。
- 外部 GMF 未送，未來除非機制改變，不應再沿 KD + 權重平均加測。
- 後續通用顯微邊界忠實度的研究線見 R42。
- 文件以繁體中文為主。
