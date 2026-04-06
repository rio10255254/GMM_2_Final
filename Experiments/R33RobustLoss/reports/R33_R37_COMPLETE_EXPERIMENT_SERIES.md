# R33-R37 完整實驗系列報告

**日期**: 2026-04-05 ~ 2026-04-06
**目標**: 打破 R30 baseline 的 0.8px step_std = 0.167862，同時盡可能保留視覺銳度
**最終結果**: GMF step_std -29% 達成（R33），但銳度 -32% 的 trade-off 經五輪實驗驗證為根本性限制

---

## 實驗總表

| Round | 分支 | 機制 | 0.8px step_std | 銳度 (grad) | 0.8px outer res_std | 結果 |
|-------|------|------|---------------|------------|---------------------|------|
| R30 baseline | baseline/r30 | B1 dironly | 0.205 | 3.46 | 2.599 | production baseline |
| **R33 hard_p95** | **sandbox/r33** | **Winsorize W_GRADMAG+W_HF_LAP at p95** | **0.129 (-37%)** | **2.36 (-32%)** | **2.905** | **External GMF -29%, BEST** |
| R33 hard_p90 | sandbox/r33 | Winsorize at p90 | 0.146 (-29%) | — | 2.765 | 次佳，8px 退步 |
| R33 lap_only | sandbox/r33 | 只截 W_HF_LAP | 0.350 (+71%) | — | 6.619 | 徹底失敗 |
| R33 softclip | sandbox/r33 | Charbonnier soft-compression | 0.144 (-30%) | 2.29 (-34%) | 2.905 | 比 hard 差 |
| R34 freq-split | sandbox/r34 | loss 層 Gaussian 分頻 | 0.141 (-31%) | 2.36 (-32%) | 3.940 | 無改善，8px 退步 |
| R35 alpha025 | sandbox/r35 | Physics layer alpha 0.10→0.25 | 0.229 (+12%) | 2.33 (-33%) | 4.764 | 失敗，artifact |
| R37 freqreg | sandbox/r37 | PSF 頻率依賴正則化 | 0.138 (-33%) | 2.29 (-34%) | 3.876 | 比 R33 差 |

---

## 外部 GMF 驗證結果（僅 R33 hard_p95 送外部）

| 尺度 | R30 baseline | R33 p95 | 改善 |
|------|-------------|---------|------|
| **0.8px** | 0.167862 | **0.119049** | **-29.1%** |
| 0.08px | 0.157720 | 0.086274 | -45.3% |
| 8px | 0.205193 | 0.153343 | -25.3% |

---

## 每輪的核心發現

### R33：Winsorize 空間損失（成功）

**假說**：residual_std ~2.9 px 的瓶頸源於不可修復缺陷像素（~8% of annulus）的離群梯度。

**結果**：
- 假說驗證成功：inner residual_std -16%，step_std -37%
- 但 outer residual_std +6%，視覺銳度 -32%
- 深度空間分析揭示：R30 最銳的 90 個角度（top 25%）梯度被壓 -41%，中等和弱角度反而提升 +27~32%
- 外邊界幀間一致性 CV 從 64% 降到 35%（GMF 改善核心）

**trade-off 本質**：Winsorize 讓邊界「柔但一致」→ GMF 在乎位置穩定不在乎銳度

### R33 ablation：lap_only（失敗）

**目的**：只截 W_HF_LAP (0.15)，保留 W_GRADMAG (0.8) 完整信號。

**結果**：catastrophic failure。W_HF_LAP 太弱（佔 total loss ~10%），截尾它幾乎不改變訓練動態。反而破壞高頻學習平衡，連基本邊緣都學不好。

**結論**：W_GRADMAG 的 Winsorize 是核心機制，不能移除。

### R33 ablation：softclip（失敗）

**目的**：用 Charbonnier soft-compression 取代硬截尾，保留方向信號。

**結果**：比 hard 更差。銳度 -34%（hard -32%），step_std 0.144（hard 0.129），8px k2 退化到 volatile_risk。

**結論**：衰減後的離群信號反而干擾一致性模式。硬截尾給模型「完全不管這些像素」的明確信號更有效。

### R34：loss 層頻域分離（失敗）

**假說**：在 gradient_magnitude_loss 內用 Gaussian blur (σ=1.5) 分頻：lo 截尾（穩定位置）、hi 不截（保留銳度）。

**結果**：銳度和 R33 完全一樣（-32%），8px 嚴重退步（0.370）。

**根因**：256×256 patch 上 lo/hi 的 Sobel 梯度高度相關。缺陷角度在兩個頻段都產生大梯度，un-capped hi loss 無法恢復銳度。

**結論**：在 spatial domain 的 loss 層做頻域分離無效。

### R35：Physics layer alpha 提升（失敗）

**假說**：alpha 0.10→0.25 讓 physics layer 做更多反卷積，encoder 收到更乾淨輸入。

**結果**：所有指標退步。step_std +12%，8px catastrophic（1.645），residual_std 暴漲 +83%。

**根因**：均勻提升 alpha 在所有頻率放大反卷積——包括噪聲敏感的高頻——引入 artifact 腐蝕 encoder 訓練。

**結論**：需要頻率選擇性，不是均勻放大。

### R37：PSF 頻率依賴正則化（失敗）

**假說**：在 Wiener 反卷積中用頻率依賴的 reg（低頻高 reg、高頻低 reg），讓 physics layer 在頻域直接分離位置穩定和邊緣銳度。

**結果**：比 R33 差。step_std 0.138（R33: 0.129），銳度 -34%（R33: -32%），8px k2 退化到 volatile_risk。

**根因**：降低高頻 reg（10→3）讓 Wiener 在高頻更激進，但同時放大了高頻噪聲。encoder 收到更噪的信號 → 更多梯度離群值 → Winsorize 截更多 → 反而更糊。

**結論**：Wiener 反卷積的高頻噪聲放大是根本限制，不能靠降低 reg 繞過。

---

## 關鍵洞察

### 1. 銳度-穩定性 trade-off 是根本性的

在目前的架構下（single-crop + spatial loss + Wiener physics），銳度和幀間穩定性不可同時改善：
- 銳利邊緣 = 高梯度 = 幀間變異大 = step_std 高
- 柔邊緣 = 低梯度 = 幀間一致 = step_std 低
- 所有試圖「只壓某些像素/頻段的銳度」的嘗試都以失敗告終

### 2. Winsorize 的效果來自「均勻化」

R33 的成功不是因為它壓制了缺陷——而是因為它讓**所有邊緣的梯度更均勻**：
- R30-sharp 角度：-41%（被壓平）
- R30-mid 角度：+27%（被拉高）
- 結果：所有角度趨向同一個梯度水準 → 幀間一致 → GMF 穩定

任何試圖「保留 sharp 角度銳度」的嘗試都會重新引入不均勻性 → 破壞一致性。

### 3. GMF 在乎的是 edgel position，不是 pixel intensity

GMF 做 edge-based geometric model fitting。它不看梯度大小——只看邊緣點在哪。柔但一致的邊緣比銳但位置不穩的邊緣更好。

### 4. 下一步方向必須跳出 single-crop + spatial loss 框架

以下方向可能打破僵局（但需要更大的架構改變）：
- **Sequence training**：直接教模型幀間一致，不靠 Winsorize 間接達成
- **雙輸出頭**：一個輸出給 GMF（穩定），一個給人眼（銳利）
- **Annulus-aware architecture**：給模型位置信息，讓它在不同區域用不同策略

---

## Checkpoint 路徑

| 候選 | 路徑 |
|------|------|
| **R33 p95 (winner)** | `Traing_Progress/..._20260405_091941/weights/best_tradeoff.pth.tar` |
| R33 p90 | `Traing_Progress/..._20260405_073906/weights/best_tradeoff.pth.tar` |
| R35 alpha025 | `Traing_Progress/..._20260405_235455/weights/best_tradeoff.pth.tar` |
| R37 freqreg | `Traing_Progress/..._20260406_004833/weights/best_tradeoff.pth.tar` |
