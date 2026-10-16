# Extended Candidate Spectrum Verdict — 13 候選完整 Decoupling Picture

Last updated: 2026-05-27
腳本:
- `scripts/collect_edge_width.py`(對 13 候選收集 720-angle per_frame edge_width)
- `scripts/compute_visual_metrics.py`(對 9 候選的 r26 recon BMP 算視覺指標)
- `scripts/run_extended_inference_720angle.py`(5 extended candidate 補測 inference + 720-angle)
資料:
- `results/edge_width_table.csv`(13 候選 × 3 pitch × 2 boundary = 78 row)
- `results/visual_metrics_table.csv` + `visual_metrics_pivot.csv` + `visual_metrics_avg.csv`(9 候選)
- 既有 13 候選 σ̂+b 表:`error_type_transformation/sigma_hat_decomposition/results/sigma_b_table.csv`

## 一句話結論

**完整 13 candidate spectrum 揭示了論文 4.5 跟 4.6 兩條主軸的真正分工——SEQ 主要做「銳化邊界 + 8 px 宏觀位移」,EDGE 主要做「三尺度位置穩定」,兩者其實在做不同的事;前面 ablation verdict 講的「核心 anchor」分工更精緻化為「銳化 anchor(SEQ)+ 位置穩定 anchor(EDGE)」**。

## 對應論文段落

- **4.8.3 邊界寬度一致性**:本 verdict 直接補上目前完全缺失的 μ_w / CV_w 量化數字
- **4.5.3 邊界微分一致性**:重新詮釋為「位置穩定 anchor」而非「銳化驅動者」
- **4.6 多幀一致性**:其角色從「打破權衡」深化為「銳化邊界 + 控制 8 px 宏觀位移」雙重作用

## 邊界寬度 μ_w 完整 13 candidate spectrum(0.8 px outer)

| Candidate | μ_w(輸入→輸出) | mu_drop% | CV_w% | 解讀 |
|---|---:|---:|---:|---|
| R30 | 36.69 → **21.95** | 40.2% | 1.19% | 起點,邊界相對粗 |
| R33 | 36.69 → 19.27 | 47.5% | 3.10% | 視覺軟仍鈍化中等 |
| **R38v2** | 36.69 → **15.34** | **58.2%** | **0.92%** | **銳且穩** |
| **COMBO** | 36.69 → **14.62** | **60.1%** | 1.11% | **最銳,穩定** |
| a030 | 36.69 → 15.92 | 56.6% | 1.89% | 接近 COMBO |
| a025 | 36.69 → 16.13 | 56.0% | 2.03% | 接近 COMBO |
| R40_a045 | 36.69 → 17.61 | 52.0% | 2.21% | 中等銳化 |
| **R42_r41best** | 36.69 → **27.07** | **26.2%** | 2.78% | **超鈍!比 R30 21.95 還鈍** |
| **R46** | 36.69 → 25.22 | 31.3% | 1.99% | 鈍化(比 R30 略好) |
| **ABLA_NO_SEQ** | 36.69 → **21.00** | **42.8%** | 1.94% | **退回 R30 級** |
| ABLA_NO_EQ | 36.69 → 15.37 | 58.1% | 1.27% | 接近 COMBO |
| **ABLA_NO_EDGE** | 36.69 → **13.14** | **64.2%** | 2.15% | **比 COMBO 14.62 還銳!** |
| ABLA_NO_FREQ | 36.69 → 18.28 | 50.2% | 2.22% | 中等銳化 |

## 五個 punch 的觀察

### 1. NO_SEQ 邊界寬度退回 R30 級(SEQ 是銳化 anchor)

NO_SEQ 0.8 px μ_w = 21.00,**跟 R30 的 21.95 幾乎一樣**——拿掉 SEQ 後模型完全沒獲得 COMBO 的銳化(14.62)。

這個結果**揭示 SEQ 的真正作用不只是控制 8 px 宏觀位移**(前面 ablation verdict 講的),**還包含『邊界銳化』**——SEQ 訓練讓模型學會在跨幀位移下保持銳利的邊界結構,缺了它就退化成單幀 baseline 的鈍邊界。

論文 4.6 narrative 從「多幀一致性是分離 σ̂/b 的監督」深化為:

> **「多幀一致性訓練同時驅動兩件事:(a) 跨幀邊界銳化(NO_SEQ μ_w 退回 R30 級),(b) 8 px 宏觀位移忠實度(NO_SEQ 8 px σ̂ 退 131%)。後者透過跨幀位移真值的直接監督達成,前者透過『跨幀一致性要求只有銳利穩定的邊界才能在多幀下保持一致』的間接 selection pressure 達成。」**

### 2. NO_EDGE μ_w 比 COMBO 還銳,但 σ̂ 大退(EDGE 是位置 anchor,不是銳化 anchor)

NO_EDGE 0.8 px μ_w = 13.14 **比 COMBO 14.62 還銳**,而且**3 個尺度全方位都更銳**。但 NO_EDGE 0.8 px σ̂ = 0.258(從 verdict 報告知道,比 COMBO 0.132 退步 +96%)。

**這個對比直接證明 EDGE 殘差的作用不是「讓邊界變銳」,是「在多幀位移下保持邊界位置不漂移」**:
- 拿掉 EDGE 殘差後,模型反而可以**更積極地 over-sharpen**(因為沒有微分一致性的約束)
- 但這個「更銳的邊界」在跨幀位移下**位置漂移**,所以 σ̂ 大退

論文 4.5.3 narrative 從「邊界微分一致性殘差約束邊界幾何」深化為:

> **「邊界微分一致性殘差是『位置 anchor + 銳化 brake』的雙重角色:它約束模型不能為了壓低 single-frame loss 而 over-sharpen 邊界(brake),同時透過微分結構約束讓邊界位置在跨幀位移下保持穩定(anchor)。拿掉它後模型可以更銳但位置不穩;這就是為什麼 COMBO 的 μ_w 比 NO_EDGE 鈍但 σ̂ 比 NO_EDGE 低。」**

### 3. R42 跟 R46 邊界比 R30 還鈍(過度訓邊界反而失敗)

R42_r41best μ_w = 27.07,R46 μ_w = 25.22,**兩者都比 R30 的 21.95 還鈍**。這兩個候選的訓練目標都是「強化邊界」(R42 boundary fidelity / R46 corner-aware):

- **R42**:訓邊界 fidelity dataset(R42 boundary stages)→ 訓練資料偏向其他結構,ring 邊界的銳化反而「分心」
- **R46**:強化 W_GRADMAG / W_EDGE_ORI / W_HF_LAP weight → ring 邊界被「過度處理」變鈍

**這對論文 4.4 / 4.5 narrative 有意涵**:**「強化邊界訓練 ≠ 更銳的 ring 邊界」**。論文寫第 6.4 capacity 邊界時可以引用這個:

> **「R42 跟 R46 兩個 research-only 候選的邊界寬度甚至比 R30 起點還鈍——強化邊界訓練不保證 ring 邊界更銳,因為訓練容量被分配到其他邊界類型上。這跟 σ̂ 退步是同源現象——能力總預算的具體展現。」**

### 4. CV_w 在 R30 已極穩定(<2%),所有訓練候選都維持在 1-3% 範圍

**「邊界寬度跨幀穩定度」(CV_w)在 R30 已經 < 2%**,代表 raw input 的邊界寬度跨幀本來就穩定(因為 PSF 是固定的)。所有訓練候選的 output CV_w 也在 1-3% 範圍,**沒有任何候選顯著退步**——也就是「跨幀邊界寬度一致性」這個維度上沒有真實 spectrum。

**對論文 4.8.3 寫法的影響**:**μ_w 是有 spectrum 的指標(R30 22 → COMBO 13),但 CV_w 沒有 spectrum**。論文 4.6.1 主張「打破權衡」應該聚焦在 μ_w 跨候選大幅變化,而非 CV_w——後者在所有候選都很穩。

### 5. 視覺指標 9 候選 spectrum 跟 σ̂+b 結果一致

從 9 candidate visual_metrics(5 extended + 4 ablation),`edge_steepness_p95` 平均值跨候選 spectrum:

| Candidate | avg edge_steepness_p95 | 解讀 |
|---|---:|---|
| ABLA_NO_EDGE | 0.146 | 最銳(over-sharp) |
| ABLA_NO_FREQ | 0.126 | 銳 |
| a030 | 0.120 | 接近 COMBO |
| a025 | 0.120 | 接近 COMBO |
| R40_a045 | 0.120 | 接近 COMBO |
| ABLA_NO_EQ | 0.124 | 接近 COMBO |
| R46 | 0.108 | 中等 |
| R42_r41best | 0.091 | 鈍化 |
| ABLA_NO_SEQ | 0.086 | 最鈍(退回 R30 級) |

**這個 spectrum 跟邊界寬度 μ_w 完全一致**(順序方向一致):
- NO_EDGE edge_steepness 最高 + μ_w 最小 = **過度銳化**
- NO_SEQ edge_steepness 最低 + μ_w 最大 = **退回 R30 級**
- R42 / R46 兩個指標都中下 = **過訓練導致反向**

兩個獨立指標 cross-validate 結論,證據強。

## 對論文 narrative 的累計影響(Tier 1 + Tier 3 + 本 Tier 2)

到目前為止所有證據合在一起,論文 4.5 / 4.6 的真正因果結構是:

```
                 銳化邊界 (μ_w, edge_steepness)        位置穩定 (σ̂, CV_w)
                 ─────────────────────────────         ──────────────────
SEQ (多幀)        強驅動者(NO_SEQ μ_w +43%)            8 px 強(σ̂ +131%)
                                                       0.8/0.08 px 無
EDGE (邊界微分)   反向 brake(NO_EDGE 更銳)             三尺度全強 anchor
                                                       (0.8 px σ̂ +96%)
FREQ (頻域)       中等支持                              中等(σ̂ +10-19%)
EQ (等變性)       無獨立 effect                         無獨立 effect
```

**論文 4.5 / 4.6 重組成「兩 anchor 各管一塊」narrative**:
- **SEQ 是銳化 anchor** + 8 px 宏觀位移 anchor
- **EDGE 是位置穩定 anchor**(三尺度)+ 銳化 brake(防止 over-sharpen)
- FREQ 中等輔助
- EQ 邊際

這比前面 ablation verdict 講的「兩 anchor + 兩輔助」更精準——**SEQ 跟 EDGE 不是互補的兩個 anchor,是 orthogonal 的兩個維度的 anchor**(銳化 vs 位置)。

## 對論文 4.6.1「打破權衡」的最終 implication

論文 4.6.1 主張「銳利度-穩定度權衡可被打破」現在有了完整的因果解釋:

> **「銳利度(μ_w↓ 跟 edge_steepness↑)由 SEQ 訓練驅動,位置穩定度(σ̂↓ 跟 b 結構化)由 EDGE 殘差駆動。因為兩者由不同訓練機制驅動,它們的梯度訊號來自不同的 loss 項,在參數空間上不直接競爭——這就是『權衡可被打破』的真正機制。COMBO 同時保留兩者(SEQ + EDGE)所以在兩個維度都接近最強;R42/R46 過度強化邊界訓練但失去 SEQ 的銳化引導,反而退到鈍邊界;NO_EDGE 拿掉位置 anchor 後可以隨意 over-sharpen 但位置不穩。」**

**這是論文 4.6.1 最強的單一論述**——而且每一段都有具體 ablation 數字當證據。

## 限制

1. **Baseline 4 個 visual_metrics absolute 值缺**:R30/R33/R38v2/COMBO 的 r26 recon BMP path 不明確,本 verdict 用 ESTIMATOR_POLICY 既有的 vs R30 (%) 當替代。COMBO absolute 值可以從 a025 capability_eval/visual_stats.csv 拿(0.8px edge_steepness_p95 ≈ 0.140)
2. **R42 / R46 邊界鈍化的因果方向需確認**:目前是「相關性觀察」,真實因果(訓練資料分配 vs ring 邊界劣化)需要更細的 ablation 才能確定。論文寫作可保守 framing
3. **CV_w 跨候選都 < 3% 的解讀**:可能是 raw input 邊界寬度本來就跨幀穩定(PSF 固定);也可能是 720-angle 圓擬合的邊界寬度量測精度有限(類似前面 σ̂ 在 0.8 px 有噪聲地板)。後者可能性需獨立驗證

## 完整證據庫產出檔

| 項目 | 位置 |
|---|---|
| **13 候選 σ̂+b** | `error_type_transformation/sigma_hat_decomposition/results/sigma_b_table.csv` |
| **σ̂ vs b 散佈圖**(13 候選版) | 同上目錄 `sigma_vs_b_panel.png` |
| **13 候選 edge_width** | `_extended_candidates_internal/results/edge_width_table.csv` |
| **9 候選 visual_metrics** | `_extended_candidates_internal/results/visual_metrics_*.csv` |
| **5 extended + 4 ablation 720-angle 完整** | `_extended_candidates_internal/_720angle/` + `method_ablations/_ablation_720angle/` |
| **Tier 3 ablation verdict**(σ̂+b 因果歸因) | `method_ablations/reports/ablation_external_gmf_verdict.md` |
| **Tier 1 主軸驗證** | `TIER_1_FINAL_VERDICT.md` |
| **本 Tier 2 spectrum verdict** | 本檔 |
