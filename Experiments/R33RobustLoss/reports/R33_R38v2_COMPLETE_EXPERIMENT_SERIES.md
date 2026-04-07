# R33-R38v2 完整實驗系列報告

**日期**: 2026-04-05 ~ 2026-04-07
**目標**: 打破 R30 baseline 的 0.8px step_std = 0.167862，同時保留視覺銳度
**最終結果**: 兩條成功路線——R33（GMF 極致型）和 R38v2（均衡型）

---

## 完整實驗總表（12 個候選，跨 7 個 Round）

| # | Round | 候選 | 機制 | 0.8px step | Gradient | Steepness | 結果 |
|---|-------|------|------|-----------|----------|-----------|------|
| 1 | R33 | hard_p90 | Winsorize all at p90 | 0.146 int | — | — | 次佳 |
| **2** | **R33** | **hard_p95** | **Winsorize all at p95** | **0.119 ext** | **2.36 (-32%)** | **3.16 (-22%)** | **GMF 極致型** |
| 3 | R33 | lap_only_p95 | 只截 Laplacian | 0.350 int | — | — | 徹底失敗 |
| 4 | R33 | soft_p95 | Charbonnier softclip | 0.144 int | 2.29 (-34%) | — | 比 hard 差 |
| 5 | R34 | freq_split_s15_p95 | loss 層 Gaussian 分頻 | 0.141 int | 2.36 (-32%) | — | 無改善 |
| 6 | R35 | alpha025_p95 | Physics alpha 0.25 | 0.229 int | 2.33 (-33%) | — | 失敗 |
| 7 | R37 | freqreg_p95 | PSF 頻率依賴 reg | 0.138 int | 2.29 (-34%) | — | 比 R33 差 |
| 8 | R38 | seq_only | Seq training 全 stages | 0.159 int | 2.26 (-35%) | 4.41 (+9%) | 8px 好，0.8px 弱 |
| 9 | R33c | stat03 | W_STAT 0.05→0.30 | 0.175 int | 2.23 (-36%) | — | 失敗 |
| **10** | **R38v2** | **8px_gate** | **Seq 8px only + gate + warmup** | **0.134 ext** | **2.67 (-23%)** | **7.67 (+89%)** | **均衡型** |

---

## 兩個成功候選的比較

| 維度 | R30 baseline | R33 hard_p95 | R38v2 8px_gate |
|------|-------------|-------------|---------------|
| **0.8px GMF (external)** | 0.167862 | **0.119049 (-29.1%)** | 0.134205 (-20.1%) |
| **8px GMF (external)** | 0.205193 | 0.153343 (-25.3%) | **0.143988 (-29.8%)** |
| 0.08px GMF (external) | 0.157720 | **0.086274 (-45.3%)** | 0.106457 (-32.5%) |
| **Edge steepness** | 4.05 | 3.16 (-22%) | **7.67 (+89%)** |
| **Edge contrast** | 89.1 | 50.8 (-43%) | **77.5 (-13%)** |
| **Contrast std** | 34.64 | 26.49 (-24%) | **30.92 (-11%)** |
| Gradient mag | 3.46 | 2.36 (-32%) | **2.67 (-23%)** |
| 8px k2 verdict | stable | moderate | **stable** |
| Lag-1 autocorr (0.8px) | +0.267 | -0.555 | -0.546 |

**R33 = GMF 精度最佳（-29%），但視覺退步。**
**R38v2 = GMF 改善 -20% 且視覺品質接近 R30（steepness +89%、contrast -13%）。**

---

## 關鍵實驗洞察

### 1. 銳度和穩定性的相關性接近零（corr = -0.107）
不穩定的原因不是銳度本身——是缺陷角度的幀間不一致。

### 2. Winsorize 的效果是「均勻化」而非「壓制」
R33 把所有角度的梯度推向同一水準 → CV 64%→35% → GMF 穩定，但銳度被犧牲。

### 3. R38v2 的 warmup 是成功的關鍵
前 15 epoch 無 seq_loss → 模型先學好完整銳度 → seq_loss 以疊加方式加入 → 不干擾銳度。

### 4. Signal-strength gate 過濾噪聲梯度是必要的
0.8px/0.08px stage 的 delta ≈ 0，注入噪聲 → R38 失敗。Gate 過濾後 → R38v2 成功。

### 5. 視覺「糊」的 90% 是邊緣轉折被平滑，不是對比度
Contrast stretching 只恢復 2pp（從 -32% 到 -30%）。W_STAT 提高反而更差。

### 6. GMF 在乎 edgel position 不在乎 pixel intensity
R33 的邊緣更窄（-6.5%）但更柔 → GMF 更好。R38v2 的邊緣更陡 → 對比度自然回升。

---

## Checkpoint 完整對照表

| Timestamp | Round | Candidate | Best Epoch | External GMF 0.8px | Status |
|-----------|-------|-----------|------------|-------------------|--------|
| 20260405_073230 | R33 | (failed launcher) | — | — | 忽略 |
| 20260405_073444 | R33 | (failed launcher) | — | — | 忽略 |
| 20260405_073906 | R33 | hard_p90 | 23 | — (internal only) | 保留 |
| **20260405_091941** | **R33** | **hard_p95** | **23** | **0.119049** | **Winner #1** |
| 20260405_114824 | R33 | lap_only_p95 | 32 | — | 否定 |
| 20260405_153826 | R33 | soft_p95 | 22 | — | 否定 |
| 20260405_225024 | R34 | freq_split_s15_p95 | 38 | — | 否定 |
| 20260405_235455 | R35 | alpha025_p95 | 38 | — | 否定 |
| 20260406_004833 | R37 | freqreg_p95 | 21 | — | 否定 |
| 20260406_122842 | R38 | seq_only | 22 | — | 保留（8px 參考） |
| 20260406_222404 | R33c | stat03 | 21 | — | 否定 |
| **20260406_235957** | **R38v2** | **8px_gate** | **54** | **0.134205** | **Winner #2** |

---

## 分支與目錄對照表

| 分支 | 實驗目錄 | 狀態 |
|------|---------|------|
| `sandbox/r33` | `Experiments/R33RobustLoss/` | Winner #1（external pass） |
| `sandbox/r33-contrast` | `Experiments/R33ContrastFix/` | 否定（contrast 更差） |
| `sandbox/r34` | `Experiments/R34FreqSplit/` | 否定 |
| `sandbox/r35` | `Experiments/R35AlphaBoost/` | 否定 |
| `sandbox/r37` | `Experiments/R37FreqReg/` | 否定 |
| `sandbox/r38` | `Experiments/R38SeqConsistency/` | 部分成功（8px 好） |
| `sandbox/r38v2` | `Experiments/R38v2SeqFixed/` | Winner #2（external pass） |

---

## 未來方向（基於深度審計）

1. **推理量化修復**（截斷→四捨五入，一行程式碼，零風險）
2. **Tiling 推理**（改善角落品質）
3. **EQ 位移分佈修正**（偏 Y 方向、覆蓋 0.8px）
4. **K=8 PSF**（減少缺陷角度）
5. **R33 + R38v2 組合**（Winsorize p95 + seq 8px gate + warmup）

詳見：`plans/ancient-sleeping-pinwheel.md`（系統架構重構計畫）
