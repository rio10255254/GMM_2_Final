# R41 結果 — 環形知識蒸餾

## 目的

R41 測試：用顯式 ring anchoring 能不能把 ring 行為拉回 COMBO 附近，同時保住 R40 拿到的 microscopy 特徵清晰度。

## 第一輪設定

- 候選：`r41_kd_from_a045`
- 起點：R40 a045 guarded 平均。
- 訓練包：700 ring、250 shape、250 microscopy 樣本。
- Ring anchor：frozen COMBO teacher。
- Microscopy anchor：frozen R40 capacity teacher。
- Shape：乾淨 label 訓練，不做 COMBO distillation。
- Epochs：30。
- Learning rate：`8e-6`。

## 接受門檻

| 檢查項 | 目標 |
|---|---:|
| external 8px step_std | ≤ `0.159` |
| external 0.8px step_std | ≤ `0.141` |
| external 0.08px step_std | ≤ `0.107` |
| micro_val_unseen PSNR | ≥ `26.0` |
| HF retention | ≥ `0.30` |

## Run Log

- 2026-05-05：R41 基礎設施建立。
- 2026-05-05：資料包 materialize 完成。
  - `r41_ring_recover_train`：1200 對 = 700 ring + 250 shape + 250 microscopy。
  - `micro_val_unseen`：100 對 held-out microscopy。
- 2026-05-05：單元測試通過（8 條）。
- 2026-05-05：CUDA 上 1 epoch / 1 batch 的 smoke run 過。
  - COMBO teacher 載入。
  - R40 teacher 載入。
  - Batch log 含 `loss_kd_combo` 與 `loss_kd_r40`。
- 2026-05-05：`r41_kd_from_a045` 正式訓練完成。
  - Run 目錄：`Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_r41_kd_from_a045_20260505_103028`。
  - Best checkpoint：`weights\best_tradeoff.pth.tar`。
  - 30 / 30 epoch 跑完。
- 2026-05-05：Held-out microscopy 驗證對 best checkpoint 跑完。
- 2026-05-05：對 best checkpoint 跑完 local 720-angle 三尺度 ring guard。
- 2026-05-05：完成 COMBO ↔ R41 權重 sweep，alpha 從 `0.10` 到 `0.40`。
- 2026-05-05：補跑高比例診斷點 alpha `0.45` / `0.50`。

## 結果

### Held-Out Microscopy 驗證

| 指標 | 結果 | 目標 | status |
|---|---:|---:|:---:|
| avg PSNR | `29.4556` | ≥ `26.0` | PASS |
| avg SSIM | `0.9513` | — | — |
| high-frequency retention | `0.7241` | ≥ `0.30` | PASS |
| edge retention | `0.9706` | — | — |
| contrast retention | `1.0026` | — | — |

逐 stage 彙總：

| stage | PSNR | SSIM | HF retention |
|---|---:|---:|---:|
| lines / grids | `21.0414` | `0.8103` | `0.9954` |
| large regions | `31.9888` | `0.9927` | `0.8170` |
| textures | `35.8366` | `0.9881` | `0.4450` |
| edge defects | `31.9914` | `0.9911` | `0.8351` |
| mixed fields | `26.4199` | `0.9745` | `0.5278` |

解讀：R41 把 R40 的 microscopy 特徵增益保住而且還有強化。它在 R41 microscopy 接受門檻上大幅超過，同樣 held-out micro target 上比 R40 a045 強。

### 直接 best checkpoint 的 local ring guard

| scale | COMBO local 參考 | R41 direct best | delta |
|---|---:|---:|---:|
| 8px | `0.1389` | `0.1628` | `+0.0239` |
| 0.8px | `0.1509` | `0.1652` | `+0.0143` |
| 0.08px | `0.1185` | `0.1543` | `+0.0358` |

解讀：直接訓練的 checkpoint 不能升級。它把 microscopy 特徵清晰度推上去了，但 local ring guard 三個尺度都退步。所以 R41 必須繼續走計畫中的 COMBO ↔ R41 權重 sweep，任何外部 GMF 升級檢查才有意義。

### COMBO ↔ R41 權重 sweep

正式 sweep：

| alpha | micro PSNR | HF retention | ring 8px | ring 0.8px | ring 0.08px |
|---:|---:|---:|---:|---:|---:|
| 0.10 | `23.2282` | `0.2293` | `0.1413` | `0.1464` | `0.1202` |
| 0.15 | `23.5350` | `0.2323` | `0.1394` | `0.1562` | `0.1326` |
| 0.20 | `23.8927` | `0.2356` | `0.1395` | `0.1598` | `0.1304` |
| 0.25 | `24.2972` | `0.2398` | `0.1503` | `0.1473` | `0.1410` |
| 0.30 | `24.7405` | `0.2457` | `0.1454` | `0.1409` | `0.1378` |
| 0.35 | `25.2092` | `0.2562` | `0.1477` | `0.1517` | `0.1294` |
| 0.40 | `25.6941` | `0.2743` | `0.1560` | `0.1481` | `0.1389` |

High-alpha diagnostic：

| alpha | micro PSNR | HF retention | ring 8px | ring 0.8px | ring 0.08px |
|---:|---:|---:|---:|---:|---:|
| 0.45 | `26.1840` | `0.3012` | `0.1577` | `0.1515` | `0.1322` |
| 0.50 | `26.6662` | `0.3358` | `0.1534` | `0.1595` | `0.1475` |

解讀：

- alpha `0.10`–`0.40` 沒有任何點同時滿足 microscopy capacity 和 ring guard。
- alpha `0.45` / `0.50` 讓 microscopy 指標過線，但 ring 0.8px 和 0.08px 不過。
- 這代表 R41 這條 COMBO ↔ R41 平均路徑沒有可升級交集。
- 因為沒有本地合格候選，本輪不送 external GMF。

## 目前 verdict

R41 訓練成功保住 microscopy 特徵 capacity，但不管是直接 checkpoint 還是 COMBO ↔ R41 平均 checkpoint，目前都沒有形成可升級候選。R41 應記為 research-only：證明 KD 可以保住 microscopy 能力，但沒有解決 ring guard 與 microscopy clarity 的共同通過問題。

外部 GMF 狀態：未送測，因為沒有本地合格候選。

下一步建議：不要再沿同一條 R41 權重平均路徑加測外部。若要開 R42，應改變機制，例如加入顯式 ring-step regression / sequence loss 作為訓練時的硬約束，而不只靠 teacher anchoring 或 post-hoc weight averaging。
