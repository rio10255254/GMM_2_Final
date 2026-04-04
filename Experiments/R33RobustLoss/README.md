# Round 33 — Residual-Guided Robust Loss

## 假說

R30 B1 dironly 的 residual_std ≈ 2.9 px 是 step_std 的主要瓶頸。
分析顯示 ~8% 的 annulus 角度有不可修復的實體缺陷（persistence = 1.0），
這些像素在 gradient magnitude loss（W_GRADMAG = 0.8）中產生離群梯度，
拉扯模型偏離對乾淨區域的優化。

如果對空間損失做 Winsorize（截尾）來降權離群像素，
模型將把學習容量集中在可改善的乾淨區域 →
乾淨角度的 residual_std 下降 → overall step_std 改善。

## 設計原則

- **R30 recipe 完全不變**：不改任何 loss 權重、schedule、架構
- **只新增一個機制**：per-pixel Winsorize on gradient magnitude + Laplacian HF loss
- **預設行為等價原行為**：`ROBUST_LOSS_PERCENTILE=1.0` = 不截斷
- **warmup**：前 N epoch 不啟用，讓模型先穩定學基本特徵

## 和先前 Rounds 的差異

| Round | 改了什麼 | 類型 | 結果 |
|-------|---------|------|------|
| R31 | loss weight (EQ prob/weight, edge ratio) | 訓練信號強度 | 外部退步 6-10% |
| R32 | 訓練資料分佈 (domain rebalancing) | 資料策略 | 外部暴增 97.7% |
| **R33** | **loss 內部的統計行為 (Winsorize)** | **穩健統計** | TBD |

## 實驗候選

| Tag | ROBUST_LOSS_PERCENTILE | ROBUST_LOSS_WARMUP | 說明 |
|-----|------------------------|--------------------|------|
| `r33_robust_p90` | 0.90 | 10 | 主候選：cap 前 10% 離群值 |
| `r33_robust_p85` | 0.85 | 10 | 激進版：cap 前 15% |
| `r33_robust_p95` | 0.95 | 10 | 保守版：只 cap 前 5% |

## 成功指標

1. **內部 gate**：pairmix + edge_band_refine 必須通過
2. **分析指標**：0.8px dataset 的 residual_std < 2.7（目標 < 2.4）
3. **外部 GMF**：0.8px step_std < 0.167862（only if internal improves）

## 失敗條件

- 內部 gate 失敗 → 立即停止
- residual_std 反而上升 → Winsorize 砍到有意義信號，回退
- 三個候選全部無改善 → 結論是 loss robustness 不是瓶頸

## 目錄結構

```
R33RobustLoss/
├── README.md          ← 本文
├── configs/           ← 訓練配置
├── scripts/           ← 啟動腳本
├── reports/           ← 結果分析報告
└── results/           ← 訓練產出（checkpoint 另存）
```

## 依賴

- Production baseline checkpoint: `r30_b1_dironly best_tradeoff.pth.tar`
- 訓練環境: 同 R30（Python 3.12.9, PyTorch 2.3.0+cu121）
- PSF: 使用 current standard Whole-FOV PSF
