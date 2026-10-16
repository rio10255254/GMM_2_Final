# Round 46 — a025 邊角細節微調(路徑 B:既有 hyperparam 強化版)

## 假說

以 a025 為起點,用低學習率微調並強化既有「邊緣銳度 / 高頻保留」相關權重(`W_GRADMAG`、`W_EDGE_ORI_SIMPLE`、`W_HF_LAP`、`W_EDGELOCAL_LAP_END`),能在維持外部 GMF 三尺度通過 3% 上限的前提下,把 a025 的邊角 / 細節還原能力往 a043 方向推進一些。

預期整體影像品質增益 +0.6 到 +1.0 分貝,角點保留率小幅改善,**不會讓直角變回完美直角、小三角形仍無解**(物理上限)。

## 動機與背景

a025 為 approved alternate(`r39r40_complementary_avg_a025`,2026-05-11 升級),是 R39 a030 跟 R40 a043 的 α=0.25 權重平均。前 三輪 Rayleigh 診斷確認:

- 驗證集 76.8% 樣本落在可解析尺度,a043 在這些樣本上系統性勝過 a025
- a043 大贏的主要方向:R40 stage_31(紋理)、stage_30(大區塊)、stage_33(混合場景),贏 2.5 ~ 3.5 分貝
- 「直角變圓」是 PSF 物理事實,a043 / a025 已接近物理下限(曲率半徑約 5 像素)
- 「三角形變一坨」是次解析尺度(< 11.7 像素)的物理上限,任何模型救不回

R46 的精神是:**不重新發明 corner-aware loss,而是用既有訓練架構把 a025 推向 a043 已驗證的方向**。

## 設計(路徑 B)

| 設定 | 值 | 為什麼 |
|---|---|---|
| 起點 checkpoint | a025 best_tradeoff.pth.tar | 平衡 R39 形狀泛化 + R40 顯微細節 |
| 訓練資料 | `r40_micro_capacity_train`(1300 對) | 包含 550 環形 + 350 R39 形狀 + 400 R40 顯微,跟 a043 訓練同 profile |
| 學習率 | 4.0e-6 | 跟 R44C low_motion_static_guard 同 order;微調而非從頭訓 |
| 訓練輪數 | 15 epoch | 跟 R44E 短探針同 order |
| `W_GRADMAG` | 1.0(基準 0.8) | 強化梯度幅值 → 邊緣銳度 |
| `W_EDGE_ORI_SIMPLE` | 0.4(基準 0.3) | 強化邊緣方向 → 直邊保留 |
| `W_HF_LAP` | 0.20(基準 0.15) | 強化高頻 Laplacian → 細節保留 |
| `W_EDGELOCAL_LAP_END` | 0.08(基準 0.06) | 強化邊緣局部高頻 |
| `EDGELOCAL_LAP_RAMP_E1/E2` | 2 / 10(基準 6 / 20) | 早一點開始 ramp,短訓練輪數需要 |
| `BOUNDARY_GEOM_ENABLE` | False | R40 train profile 不含 geom,不開 |
| `MOTION_ENABLE` / `SEQ_ENABLE` / `KD_ENABLE` | 全 False | R46 不是位移 / KD 線 |
| `ROBUST_LOSS_PERCENTILE` | 0.95 | 跟 a025 訓練一致 |
| 環形 replay 守門 | 由訓練資料中 550 對環形樣本提供 | 守外部 GMF 三尺度通過 3% |

## 候選

| Tag | 起點 | 訓練資料 | 角色 |
|---|---|---|---|
| `r46_a025_corner_finetune` | a025 best_tradeoff | r40_micro_capacity_train | 主候選:既有 hyperparam 強化版 |

## 評估流程

訓練完成後跑:

1. **R39 shape_val_unseen 七類重建**(210 對),算 PSNR / SSIM / 邊界 F1 / 角點保留 / 形狀錯誤
2. **R40 micro_val_unseen 五類重建**(100 對),同樣指標
3. **Rayleigh 診斷**:複用 `rayleigh_diagnostic.py`,看可解析尺度 / 次解析尺度上 R46 比 a025 改善多少
4. **配對 t 檢定** R46 vs a025:看每個指標每個分桶上是否統計顯著
5. **R44G 邊界形狀體檢**(角點 / 直邊保留)
6. **本地三尺度 ring guard**:確認沒洗掉 ring 能力
7. **視覺驗證**:挑紋理大贏 case、矩形直角、小三角形做五聯對比(GT / COMBO / a043 / a025 / R46)

## 升級門檻

| 指標 | 升級門檻 |
|---|---|
| R40 micro_val_unseen 整體 PSNR vs a025 | ≥ +0.5 dB |
| R39 shape_val_unseen 整體 PSNR vs a025 | ≥ +0.3 dB |
| 角點保留 vs a025 | ≥ +0.5 個百分點(配對 t 檢定 p < 0.05) |
| 本地 ring guard 8 / 0.8 / 0.08 px | 三尺度都通過 3% 上限(維持 a025 等級) |
| 外部 GMF(如果有送) | 三尺度都通過 3% 上限 |

未達門檻 = 研究紀錄,不升級。

## 分支

當前 worktree:`claude/gifted-shaw-29b50a`(跟 origin/main 同步)

R46 實驗目錄在 `Experiments/R46_CornerAwareFineTune/`(跟 R39-R45 一樣,目前 untracked,完成後再評估是否 commit)

## 結果

(訓練完成後填寫,參見 `reports/R46_RESULTS.md`)
