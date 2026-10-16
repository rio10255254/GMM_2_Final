# R41 — 環形知識蒸餾

## 假說

R40 證明合成顯微特徵覆蓋能把 capacity 推上去，但訓練 endpoint 的 ring guard 都不過。R41 假說是：用顯式 teacher anchoring（COMBO 守 ring、R40 守 microscopy capacity），能在不毀掉 microscopy 細節的前提下把 ring 行為拉回 COMBO 附近。

## 設計

R41 不改模型本體。從 R40 a045 guarded 平均接續，加入兩個 frozen teacher 與一個受控 replay 訓練包。

- Ring teacher：frozen COMBO，做 ring 樣本的 logits 牽引
- Microscopy teacher：frozen R40 capacity 端點，做顯微樣本的 logits 牽引
- Shape：乾淨 label，不做 KD
- Learning rate：`8e-6`
- Epochs：30

## 候選

| 候選 | 起點 | 角色 |
|---|---|---|
| `r41_kd_from_a045` | R40 a045 guarded 平均 | 主要候選；30 epoch 完整訓練 |

## 資料

| 資料包 | 對數 | 組成 |
|---|---:|---|
| `r41_ring_recover_train` | 1200 | 700 ring + 250 shape + 250 microscopy |
| `micro_val_unseen` | 100 | held-out microscopy |

## 接受門檻

| 檢查項 | 目標 |
|---|---:|
| external 8px step_std | ≤ `0.159` |
| external 0.8px step_std | ≤ `0.141` |
| external 0.08px step_std | ≤ `0.107` |
| micro_val_unseen PSNR | ≥ `26.0` |
| HF retention | ≥ `0.30` |

## 流程

訓練：

```powershell
python Experiments\R41_RingDistillation\scripts\launch_r41.py --candidate r41_kd_from_a045 --build-data --num-epoch 30 --device cuda:0
```

評估：

- `scripts/run_r41_micro_recon.py` — held-out microscopy 重建
- `scripts/run_r41_ring_guard.py` — local 720-angle ring guard
- `scripts/run_r41_weight_sweep.py` — COMBO ↔ R41 權重 sweep
- `scripts/r41_external_compare.py` — 外部 GMF parser

## 升級規則

R41 是研究路線。要升級必須同時滿足：

- 微觀驗證：`micro_val_unseen` PSNR ≥ `26.0`、HF retention ≥ `0.30`。
- 環形守門：local 三尺度 ring step_std 不能比 COMBO 退步。
- 外部 GMF：三尺度都要過接受門檻。

任何一條不過就不送外部 GMF，本輪結果只作研究紀錄。

## 結果

R41 訓練、評估、權重 sweep 都已完成。**結論：研究成功保住 microscopy capacity，但沒有形成可升級候選；不送外部 GMF。**

| 候選 | micro PSNR | HF retention | ring 8px | ring 0.8px | ring 0.08px | verdict |
|---|---:|---:|---:|---:|---:|---|
| COMBO local 參考 | — | — | `0.1389` | `0.1509` | `0.1185` | baseline |
| `r41_kd_from_a045` direct best | `29.4556` | `0.7241` | `0.1628` | `0.1652` | `0.1543` | 顯微強但 ring 三尺度退步 |
| `r41_combo_avg_a045`（高 alpha 診斷） | `26.1840` | `0.3012` | `0.1577` | `0.1515` | `0.1322` | 微觀剛過但 ring 0.8px / 0.08px 不過 |
| `r41_combo_avg_a050`（高 alpha 診斷） | `26.6662` | `0.3358` | `0.1534` | `0.1595` | `0.1475` | 微觀過但 ring 0.8px / 0.08px 不過 |

正式 sweep alpha 0.10–0.40 沒有任何 alpha 同時通過 microscopy 與 ring guard；高 alpha 診斷 0.45 / 0.50 微觀過，但 0.8px 與 0.08px ring 不過。

## 判讀

R41 證明 KD anchoring 能保住 R40 的 microscopy capacity，甚至略有強化。但「保 microscopy + 過 ring guard」這條路徑沒有共同通過點：低 alpha 守 ring 但失 capacity，高 alpha 拿到 capacity 但失 ring。這條路線到此為止，下一輪不應再沿同一條 KD + 權重平均加測。

## 下一步方向

不要再做 COMBO ↔ R41 權重平均。若要繼續推 microscopy，下一輪應改用顯式 ring-step regression 或 sequence loss 作為訓練時的硬約束，而不只靠 teacher anchoring 加 post-hoc 平均。R42 已沿此方向開出，把焦點從環形代理推向通用顯微邊界忠實度。

## 主要資料與產物

2026-08-01 起，完整候選重建、掃描權重、正式訓練過程與 R41 專用資料已核對封存到 H 槽。D 槽保留正式報告、程式、測試、數字摘要與一份代表模型。完整位置及恢復方法見 `ARCHIVE_POINTER.md`。

| 類型 | 位置 |
|---|---|
| 資料 builder | `scripts/r41_data.py` |
| 訓練啟動器 | `scripts/launch_r41.py` |
| KD 模組 | `scripts/r41_kd_module.py` |
| 微觀重建 | `scripts/run_r41_micro_recon.py` |
| Ring guard | `scripts/run_r41_ring_guard.py` |
| 權重 sweep | `scripts/run_r41_weight_sweep.py` |
| 外部比較 | `scripts/r41_external_compare.py` |
| 主結果報告 | `reports/R41_RESULTS.md` |
| 外部紀錄 | `reports/R41_EXTERNAL_COMPARE.md` |
| 訓練 run | 已封存；見 `ARCHIVE_POINTER.md` |
| D 槽代表模型 | `selected_checkpoint/best_tradeoff.pth.tar`（研究用途，未升級） |
| Direct best 摘要 | `results/micro_recon/r41_kd_from_a045_best_summary.json` |
| Ring guard 摘要 | `results/ring_guard/r41_kd_from_a045_best_ring_guard_summary.json` |
| 正式 sweep | `results/weight_sweep/sweep_summary.md`；完整重建與 checkpoint 已封存 |
| 高 alpha 診斷 | `results/weight_sweep_ext_high_alpha/sweep_summary.md`；完整重建與 checkpoint 已封存 |

## 分支

`sandbox/r41`
