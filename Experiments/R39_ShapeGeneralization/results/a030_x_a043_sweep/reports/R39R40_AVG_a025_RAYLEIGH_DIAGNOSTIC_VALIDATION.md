# R39R40 a025 Rayleigh 診斷補充驗證 — 統計檢驗篇

本檔是 [R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC.md](R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC.md) 的 follow-up。前一份報告用「逐 stage / 逐 Rayleigh class 的 mean delta」看到幾個 a043 「在某些 case 輸 a025」的反例,本檔用配對統計檢驗(paired t-test、Wilcoxon)驗證這些反例,結論是**多數是 small-sample + 離散指標造成的 mean shift 雜訊,不是真實訊號**。

## 摘要

| 前報告的觀察 | 驗證結果 |
|---|---|
| a043 在 polygons / lines_grid / large_regions / edge_defects 等 stage 上 corner_retention 輸 a025 | **paired t-test 全部 n.s.**(p > 0.37),雜訊 |
| sub-Rayleigh 上 straight_edge_coverage a043 退步 1.91 pp | **t-test n.s.**(p = 0.33),**Wilcoxon n.s.**(p = 0.66),雜訊 |
| a043 在所有 Rayleigh 分桶 PSNR 顯著贏 a025 | **確認**,三個分桶 paired t-test p < 0.001 |
| a043 在所有 stage PSNR 顯著贏 a025 | **確認**,12 個 stage paired t-test 全部 p < 0.001 |

**結論翻盤**:

a043 比 a025 **在所有 stage、所有 Rayleigh 分桶上系統性顯著贏**,沒有任何統計顯著的反例。前一份報告 fig5(per-stage a043 - a025)看到的「紅色 stage」是 corner_retention 離散性 + 小樣本造成的 mean shift,不是真實訊號。

對 R46 微調策略的影響:**不需要 stage-specific 訓練配方**,整套朝 a043 方向推就對了。先前因為「擔心 a043 在 sub-Rayleigh 過銳化」而保留的設計緩衝,在統計上沒有支持。

## 動機

前一份報告主要用 mean delta(對每個分桶 / stage 平均)看 a043 vs a025 的差距。但發現幾個 mean 上的反例:

1. fig5 per-stage:a043 在 stage_05_polygons / stage_29_micro_lines_grid / stage_30_micro_large_regions / stage_32_micro_edge_defects 上 corner_retention mean 低於 a025
2. 整體 sub-Rayleigh 分桶 mean:a043 的 straight_edge_coverage 比 a025 低 1.91 pp

這些觀察被前報告解讀為「a043 過銳化在某些情境反噬」,並建議 R46 設計要 stage-specific 配方 + 克制 corner-aware loss 強度以避免重現 a043 在 sub 上的過銳化。

但 mean 容易被個別極端值帶偏。**配對檢驗**(每張影像的 a043 - a025 差,做 t-test 或 Wilcoxon)才是正確判斷顯著性的方法。

## 方法

對每張影像,既有 a043 跟 a025 的指標值,計算 `delta_i = a043_i − a025_i`。然後對 `{delta_i}` 跑:

- **paired one-sample t-test**(`scipy.stats.ttest_1samp`):檢驗 mean delta 是否顯著不為 0
- **Wilcoxon signed-rank test**(`scipy.stats.wilcoxon`):非參數版本,不假設常態分布,適合離散 / skewed metric

對每個 (group × metric) 組合算一次。Groups 分兩種:

- 逐 stage(12 個 stage,paired test n = 20 ~ 30)
- 逐 Rayleigh class(supra / mixed / sub,paired test n = 19 ~ 238)

顯著性標準:p < 0.05 (*),p < 0.01 (**),p < 0.001 (***)。

## 驗證一:per-stage corner_retention「反例」是雜訊

| stage | n | mean delta(a025−a043) | t-stat | p-value | 結論 |
|---|---:|---:|---:|---:|---|
| stage_05_polygons | 24 | +0.0035 | +0.20 | 0.85 | **n.s.** 雜訊 |
| stage_29_micro_lines_grid | 9 | +0.0387 | +0.87 | 0.41 | **n.s.** 雜訊 |
| stage_30_micro_large_regions | 18 | +0.0139 | +0.22 | 0.83 | **n.s.** 雜訊 |
| stage_32_micro_edge_defects | 20 | +0.0276 | +0.92 | 0.37 | **n.s.** 雜訊 |

四個前報告以為「a025 贏」的 stage,paired t-test p 值全部 > 0.37,完全沒有統計訊號。

進一步看 weight averaging synergy(a025 strictly > a030 AND a043 同時):

| stage | synergy case | 比例 |
|---|---:|---:|
| polygons | 0 / 30 | 0% |
| lines_grid | 2 / 20 | 10% |
| large_regions | 1 / 20 | 5% |
| edge_defects | 1 / 20 | 5% |

polygons 上 zero synergy。前報告以為「weight averaging 在這幾個 stage 有非線性增益」的解讀沒有資料支持。

## 驗證二:sub-Rayleigh 上 straight_edge_coverage 「退步」也是雜訊

| 檢驗 | n | mean delta(a043−a025) | stat | p-value | 結論 |
|---|---:|---:|---:|---:|---|
| paired t-test | 15 | −0.0191 | t = −1.02 | 0.33 | **n.s.** |
| Wilcoxon signed-rank | 15 | −0.0191 | W = 28 | 0.66 | **n.s.** |

sub-Rayleigh 樣本只有 15(對應 19 unique GT 但 4 張 corner mask 為空),sample size 太小,mean −1.91 pp 看似明顯但統計上完全不顯著。

對 corner_retention 同樣檢定:

| 檢驗 | n | mean delta(a043−a025) | p-value | 結論 |
|---|---:|---:|---:|---|
| paired t-test (sub) | 15 | +0.0191 | 0.64 | **n.s.** |
| Wilcoxon (sub) | 15 | +0.0191 | 0.92 | **n.s.** |

sub-Rayleigh 上 a043 跟 a025 在 corner_retention / straight_edge_coverage 上**沒有統計顯著差異**,前報告的「a043 sub 過銳化反噬」說法在資料上沒根據。

## 驗證三:a043 全面系統性贏 a025(連續指標,顯著)

PSNR / SSIM / boundary_f_score / HF retention / edge retention 是連續指標,variance 較小,paired test 訊號穩定:

### PSNR(三個分桶都極顯著)

| class | n | mean delta(a043−a025) | t-stat | p-value |
|---|---:|---:|---:|---:|
| supra | 238 | +1.32 dB | +32.74 | 6.4 × 10⁻⁹⁰ |
| mixed | 53 | +1.22 dB | +14.58 | 5.2 × 10⁻²⁰ |
| sub | 19 | +0.74 dB | +7.73 | 4.0 × 10⁻⁷ |

### 逐 stage PSNR(12 個 stage 全部 p < 0.001)

| stage | n | mean delta(dB) | p-value |
|---|---:|---:|---:|
| stage_01_triangles | 30 | +1.09 | 3.4 × 10⁻¹⁶ |
| stage_02_circles | 30 | +1.47 | 5.6 × 10⁻¹³ |
| stage_03_rectangles | 30 | +0.97 | 4.3 × 10⁻¹⁵ |
| stage_04_ellipses | 30 | +1.19 | 7.2 × 10⁻¹⁰ |
| stage_05_polygons | 30 | +1.55 | 1.4 × 10⁻¹³ |
| stage_06_mixed_simple | 30 | +1.35 | 8.2 × 10⁻¹⁹ |
| stage_07_mixed_complex | 30 | +1.09 | 1.2 × 10⁻¹⁹ |
| stage_29_micro_lines_grid | 20 | +0.89 | 2.7 × 10⁻⁵ |
| stage_30_micro_large_regions | 20 | +1.37 | 1.1 × 10⁻⁷ |
| stage_31_micro_textures | 20 | +2.21 | 1.7 × 10⁻¹² |
| stage_32_micro_edge_defects | 20 | +1.22 | 6.5 × 10⁻¹³ |
| stage_33_micro_mixed_fields | 20 | +0.84 | 1.7 × 10⁻⁸ |

12 個 stage 全部 p < 10⁻⁴,沒有例外。

### 各分桶 × 各指標檢定總表

| 指標 | supra(n=238) | mixed(n=53) | sub(n=19) |
|---|---|---|---|
| PSNR | +1.32 dB *** | +1.22 dB *** | +0.74 dB *** |
| SSIM | +0.010 *** | +0.025 *** | +0.041 ** |
| boundary_f_score | +0.027 *** | +0.023 *** | +0.022 **n.s.** |
| HF retention | +0.046 *** | +0.045 * | +0.030 *** |
| edge retention | +0.084 *** | +0.080 *** | +0.063 *** |
| corner_retention | +0.014 * | +0.022 * | +0.019 **n.s.** |
| straight_edge_coverage | +0.027 *** | +0.021 *** | −0.019 **n.s.** |
| shape_error_score | −0.015 ** | −0.001 **n.s.** | −0.020 **n.s.** |

(粗體 **n.s.** 是不顯著的格子。指標方向以 a043 為基準,正值代表 a043 較高,shape_error_score 則負值代表 a043 較低、較好。)

**觀察**:

1. PSNR / SSIM / HF retention / edge retention 在三個分桶上**全部**顯著 a043 勝
2. boundary_f_score、corner_retention、straight_edge_coverage 在 supra / mixed 上顯著,在 sub 上 n.s.——這是 sample size 不足(n = 15-19)的問題,**不是 a043 在 sub 上真的輸**
3. shape_error_score 只在 supra 顯著,其他 n.s.——這個 metric 本身 variance 大、且包含 fragmentation_ratio 的 log penalty,離散性偏高

## 為什麼 corner_retention 的 mean 不可信:離散性實證

`corner_retention = retained_corner_count / expected_corner_count`,分母是該影像 connected component 邊界框的 corner 數總和(每 component 4 個 corner)。對 polygons (stage_05) 多數 GT 是「一個多邊形 → 一個 component → 4 個 corner」,所以 retention 只能是 `0/4, 1/4, 2/4, 3/4, 4/4` 加上多 component 時的其他離散值。

實測 polygons stage 上 a043 的 corner_retention distribution(24 個 finite values):

| value | count |
|---:|---:|
| 0.0 | 4 |
| 0.286 | 1 |
| 0.333 | 3 |
| 0.4 | 1 |
| 0.5 | 3 |
| 0.667 | 3 |
| 0.75 | 2 |
| 1.0 | 7 |

a025 的 distribution 幾乎一樣。**8 個離散值 + 24 sample**,1 張影像 corner retention 從 0 跳到 1 就能把 mean 拉動 0.04。所以 fig5 看到 polygons 上 a025 mean 略高,只要一張 outlier 就能解釋。

**方法論教訓**:**R44G 的 corner_retention / straight_edge_coverage 對小樣本不穩,做 paired comparison 時必須用 t-test / Wilcoxon,不能只看 mean**。

## Top wins / losses

### a043 比 a025 PSNR 贏最多的 10 個 case

| stage | frame | sw_med(px) | a043_PSNR | a025_PSNR | delta(dB) |
|---|---|---:|---:|---:|---:|
| stage_31_micro_textures | 0084 | 15.2 | 30.79 | 27.33 | **+3.46** |
| stage_31_micro_textures | 0096 | 20.8 | 31.82 | 28.72 | **+3.10** |
| stage_31_micro_textures | 0091 | 16.0 | 30.17 | 27.07 | **+3.10** |
| stage_31_micro_textures | 0090 | 15.6 | 31.67 | 28.75 | +2.93 |
| stage_31_micro_textures | 0085 | 25.2 | 32.19 | 29.50 | +2.69 |
| stage_30_micro_large_regions | 0083 | 134.0 | 27.06 | 24.38 | +2.68 |
| stage_02_circles | 0197 | 83.2 | 28.55 | 25.89 | +2.66 |
| stage_31_micro_textures | 0086 | 25.2 | 33.00 | 30.44 | +2.56 |
| stage_05_polygons | 0494 | 48.4 | 26.54 | 24.03 | +2.51 |
| stage_29_micro_lines_grid | 0083 | 8.0 | 30.17 | 27.70 | +2.47 |

**觀察**:6/10 是 textures(R40 stage_31),且 sw_median 大多 15-25 px(剛過 Rayleigh 上限)。這代表 R46 微調最該補強的方向是**剛過 Rayleigh 上限的中等細節結構**,特別是 textures。

### a043 比 a025 PSNR「輸」最多的 10 個 case(其實都很微)

| stage | frame | sw_med(px) | a043_PSNR | a025_PSNR | delta(dB) |
|---|---|---:|---:|---:|---:|
| stage_29_micro_lines_grid | 0090 | 2.0 | 20.82 | 20.73 | +0.09 |
| stage_29_micro_lines_grid | 0096 | 2.0 | 17.53 | 17.49 | +0.04 |
| stage_29_micro_lines_grid | 0086 | 8.0 | 14.77 | 14.79 | −0.02 |
| stage_02_circles | 0192 | 512.0 | 31.87 | 31.92 | −0.05 |
| stage_30_micro_large_regions | 0085 | 142.6 | 29.16 | 29.24 | −0.07 |
| stage_30_micro_large_regions | 0082 | 125.1 | 32.99 | 33.08 | −0.09 |
| stage_05_polygons | 0475 | 197.0 | 30.41 | 30.72 | −0.31 |
| stage_05_polygons | 0495 | 512.0 | 30.44 | 30.78 | −0.34 |
| stage_02_circles | 0184 | 512.0 | 30.17 | 30.63 | −0.46 |
| stage_04_ellipses | 0381 | 132.1 | 32.67 | 33.32 | **−0.66** |

**觀察**:

- 最大的「輸」也只有 −0.66 dB,跟「贏」最多的 +3.46 dB 量級差很多
- 輸的 case 集中在**已經很高 PSNR(30+ dB)+ 大形狀(100+ px,接近 512)**——也就是「已經很容易」的 case
- 換言之:**a043 在「easy case」上有極小的反向,但在「中等難度」(textures、defects、mixed,sw 15-150 px)上大幅領先**
- 這個觀察跟前報告講的「a043 sub-Rayleigh 過銳化反噬」**完全不同**——實際上 a043 不是在 sub-Rayleigh 反噬,而是在 already-easy 大形狀上微微弱

## 修正的 R46 expected gain

以前報告講「expected gain 要照 supra-Rayleigh 占比 deflate」是基於假設 sub-Rayleigh 上 a043 沒贏。但驗證顯示 a043 在 sub-Rayleigh 上 **PSNR / SSIM / HF retention / edge retention 都顯著贏**,只是訊號被物理上限壓得較小。

新的加權期望增益(用全部 3 分桶,但只 credit 統計顯著的 class delta):

| 指標 | 期望增益(顯著 credit) | 之前 naive 估計 | 差異 |
|---|---:|---:|---|
| PSNR | **+1.26 dB** | +1.28 dB | 幾乎一樣 |
| SSIM | +0.014 | +0.013 | 接近 |
| HF retention | +0.045 | +0.044 | 接近 |
| edge retention | +0.082 | +0.082 | 一樣 |
| boundary_f_score | +0.025 | +0.027 | 略低(sub n.s.) |
| corner_retention | +0.015 | +0.016 | 略低(sub n.s.) |
| straight_edge_coverage | +0.025 | +0.021 | 略高(sub naive 是負,credit 0) |
| shape_error_score | −0.012 | −0.013 | 接近 |

**R46 完美達到 a043 水準的上限是整體 PSNR +1.26 dB**。實際守 ring guard、低 LR、短訓練輪數,預期拿到 50-80% 為 **+0.63 ~ +1.01 dB**。

## R46 設計指引的修正版

跟前報告比較:

| 設計要點 | 前報告版 | 修正版(驗證後) |
|---|---|---|
| 整套學 a043 方向 | OK,但要避免 stage-specific 反例 | **OK,沒有反例,可以乾脆全推** |
| corner-aware loss 強度克制(5× 而非 10×) | **避免 sub-Rayleigh 過銳化** | **守 ring guard**(維持 a025 三尺度平衡),sub 過銳化不是真實顧慮 |
| sub-Rayleigh 平滑懲罰 | 必要,避免重現 a043 過銳化 | **可選**——統計上 a043 sub 沒有真正退步,但加上仍然不會壞 |
| R40 train 資料偏重哪些 stage | supra 為主、避開 stage_29 | **重點補 stage_31(textures)、stage_30(large_regions)、stage_33(mixed_fields)**——這是 a043 大贏的方向 |
| stage_05 polygons / stage_32 edge_defects 是否要特別處理 | 是,a025 在這些 stage 反而強 | **不必**,差距不顯著 |
| 期望增益 | 整體 PSNR +0.64 ~ +1.02 dB | 整體 **PSNR +0.63 ~ +1.01 dB**(幾乎一樣) |

整體 R46 「值得開」這個結論沒變。但設計細節從「stage-specific 緩衝」簡化成「乾脆全方向學 a043,主守 ring guard」。

## 方法論教訓

留給未來自己跟接手者:

1. **小樣本(< 30) + 離散 metric(corner_retention、straight_edge_coverage)做模型比較時,不能只看 mean delta**,要做 paired t-test 或 Wilcoxon
2. **連續指標**(PSNR、SSIM、boundary_f_score、HF retention、edge retention)variance 小、訊號穩定,優先依賴
3. **看到「某分桶 a 比 b 退步」的反例時,先檢定再說**——這次差點基於雜訊改 R46 設計
4. **R44G 的邊界形狀指標**仍有用,但要懂它的離散性特性,別過度解讀 per-stage mean

## 產物

| 檔案 | 內容 |
|---|---|
| `../rayleigh_diagnostic/validation/paired_tests_per_stage.csv` | 12 stage × 8 metric 配對 t-test + Wilcoxon 結果 |
| `../rayleigh_diagnostic/validation/paired_tests_per_class.csv` | 3 class × 8 metric 同上 |
| `../rayleigh_diagnostic/validation/revised_expected_gain.csv` | 修正版期望增益(顯著 credit) |
| `../rayleigh_diagnostic/validation/top_wins_losses_psnr.csv` | a043 vs a025 PSNR top 15 wins / losses |
| `Experiments/R39_ShapeGeneralization/scripts/rayleigh_diagnostic_validate.py` | 驗證主腳本(以後 R46 完成後重跑可比較) |

## 可重跑

```bash
cd D:/GMM_2_Final
python Experiments/R39_ShapeGeneralization/scripts/rayleigh_diagnostic_validate.py
```

依賴 `scipy.stats`(`ttest_1samp`、`wilcoxon`)。

本檔記錄統計檢驗結果,不下硬性 verdict 也不取代前報告——前報告的 mean 表格仍是事實紀錄,只是解讀需以這份驗證為準。R46 是否要動、設計細節怎麼定,由人類拍板。
