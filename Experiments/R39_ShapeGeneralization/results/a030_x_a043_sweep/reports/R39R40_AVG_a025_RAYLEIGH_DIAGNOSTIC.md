# R39R40 a025 Rayleigh-aware 邊角細節診斷

> **2026-05-14 補充驗證 caveat**:本檔基於 mean delta 的部分 per-stage / sub-Rayleigh 結論(例如「a043 在 polygons / lines_grid / large_regions / edge_defects 上輸 a025」、「sub-Rayleigh 上 a043 straight_edge_coverage 退步 1.91 pp」)經配對 t-test / Wilcoxon 檢驗後**證實為雜訊**,不是真實訊號。正確的統計結論是 **a043 在所有 stage、所有 Rayleigh 分桶都系統性顯著贏 a025,沒有真正反例**。完整檢驗、新的 R46 設計建議跟方法論教訓見 [R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC_VALIDATION.md](R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC_VALIDATION.md)。本檔的數字仍是事實紀錄,但解讀以驗證篇為準。

## 摘要

針對「a025 邊角與細節還原能力是否值得進一步推進」這個問題,把 a025 capability eval 既有的 R44G 風格邊界形狀指標(corner_retention、straight_edge_coverage、shape_error_score 等)按 GT 特徵尺寸切成可解析尺度(supra-Rayleigh)、混合、次解析尺度(sub-Rayleigh)三類,對照 a043 / a030 / COMBO,釐清 a025 跟 a043 之間的差距有多少在物理上可推、多少落到 PSF 物理上限之外。

**核心發現**:

- 310 張驗證影像裡,**238 張(76.8%)落在 supra-Rayleigh 區**、53 張(17.1%)混合、19 張(6.1%)主要在 sub-Rayleigh。
- a043 比 a025 強的差距,**在 supra-Rayleigh 區段是訓練可推空間**:PSNR +1.32 dB、HF retention +4.56 pp、edge retention +8.43 pp、corner_retention +1.41 pp、straight_edge_coverage +2.73 pp、shape_error_score 改善 0.0154。
- sub-Rayleigh 區段差距較小(PSNR +0.74 dB、shape_error 改善 0.0203),且 a043 的 **straight_edge_coverage 在 sub-Rayleigh 反而比 a025 退步 1.91 pp**,顯示過銳化在次解析尺度會讓直邊出現跳斷或波紋。

**對 R46 corner-aware fine-tune 的啟示**:

- 大部分(77%)樣本的邊角失真是訓練問題,**fine-tune 有空間**。
- 推進方向應聚焦在 supra-Rayleigh 樣本,**期望整體 PSNR 增益約 +0.5 ~ +1.0 dB**(以填補 a043 vs a025 的差距上限為錨,實際 fine-tune 守 ring guard 時拿到 50-80%)。
- 對 sub-Rayleigh 樣本(6.1%)別期望大改善——物理上限在那。
- **corner-aware loss 強度要克制**:a043 在 sub-Rayleigh 的 straight_edge_coverage 退步,提示過度推高頻會在次解析尺度產生跳斷。R46 設計需要 ring replay 守邊界穩定,fine-tune 強度寧偏溫和。

## 方法

### 資料來源

- `capability_eval/per_pair_metrics.csv`:1240 列,4 模型(COMBO、a030、a043、R39R40_a025)× 310 張 GT × 既有的邊界形狀指標(shape_error_score、corner_retention、straight_edge_coverage、boundary_f_score、high_frequency_retention、edge_retention、PSNR、SSIM)。
- GT 影像:
  - R39 shape_val_unseen:210 張(7 類純幾何形狀各 30 張)
  - R40 micro_val_unseen:100 張(5 類顯微特徵各 20 張)

### Rayleigh 上限

依本專案相機光學參數:

```
d_Rayleigh = 0.61 × 550 nm / NA 0.23
          ≈ 1460 nm
          ≈ 1.46 μm
          ≈ 11.7 px       (pixel size ≈ 125 nm/px)
```

低於此距離的高頻訊號被光學系統 PSF 砍掉,任何「還原」都是 prior 驅動的猜測,不是物理意義上的還原。

### Feature width 演算法

對每張 GT label 影像:

1. 二值化:`binary = (gt > 50)`(背景 0、目標前景 ≥ 185 灰階,threshold 50 把雜訊低值過濾)
2. Skeletonize(`skimage.morphology.skeletonize`)取中軸
3. 對 binary 跑 `cv2.distanceTransform(DIST_L2, 5)`
4. **stroke width** = `distance_transform[skeleton] × 2`(每個 skeleton pixel 上的局部 stroke width)
5. 取每張影像的 `sw_median`、`sw_p25`、`sw_p75`、`sw_max`、`sub_rayleigh_frac = (widths ≤ 11.7 px).mean()`

這個算法對線狀結構(stroke width 直接 = 線寬)、大區塊(stroke width = 區塊厚度)、混合場景都有意義,且不依賴 connected component 拆分。

### 影像分桶

依每張影像的 `sub_rayleigh_frac`:

- `supra`:< 25%(大部分特徵在可解析尺度)
- `mixed`:25 ~ 75%
- `sub`:> 75%(大部分特徵在次解析尺度)

## 結果

### 影像分桶分布

| 分桶 | 影像數 | 比例 |
|---|---:|---:|
| supra | 238 | 76.8% |
| mixed | 53 | 17.1% |
| sub | 19 | 6.1% |

(4 個模型各跑同一組 310 張,分桶以 GT 為準,跟 model 無關。)

### 主指標 × 分桶 × 模型

#### shape_error_score(↓ 越低越好)

| model | supra | mixed | sub |
|---|---:|---:|---:|
| COMBO | 0.4399 | 0.4985 | 0.7838 |
| a030 | 0.3807 | 0.4157 | 0.7710 |
| **a043** | **0.3607** | **0.4177** | **0.7459** |
| **R39R40_a025** | **0.3760** | **0.4186** | **0.7662** |
| **a043 − a025** | **−0.0154** | −0.0009 | **−0.0203** |

#### corner_retention(↑ 越高越好)

| model | supra | mixed | sub |
|---|---:|---:|---:|
| COMBO | 0.4728 | 0.3297 | 0.4657 |
| a030 | 0.6124 | 0.4749 | 0.5803 |
| **a043** | **0.6378** | **0.5130** | **0.6202** |
| **R39R40_a025** | **0.6237** | **0.4908** | **0.6011** |
| **a043 − a025** | **+0.0141** | **+0.0222** | **+0.0191** |

#### straight_edge_coverage(↑ 越高越好)

| model | supra | mixed | sub |
|---|---:|---:|---:|
| COMBO | 0.6547 | 0.5893 | 0.6851 |
| a030 | 0.7317 | 0.6874 | 0.7157 |
| **a043** | **0.7694** | **0.7185** | **0.7012** |
| **R39R40_a025** | **0.7422** | **0.6978** | **0.7203** |
| **a043 − a025** | **+0.0273** | **+0.0207** | **−0.0191** |

注意 sub 區段 a043 反而退步 1.91 pp——過銳化在 sub-Rayleigh 反而傷直邊保留。

#### boundary_f_score(↑)

| model | supra | mixed | sub |
|---|---:|---:|---:|
| COMBO | 0.7518 | 0.6282 | 0.5140 |
| a030 | 0.7969 | 0.7140 | 0.5694 |
| **a043** | **0.8337** | **0.7474** | **0.6122** |
| **R39R40_a025** | **0.8062** | **0.7243** | **0.5900** |
| **a043 − a025** | **+0.0274** | **+0.0232** | **+0.0221** |

#### high_frequency_retention(↑)

| model | supra | mixed | sub |
|---|---:|---:|---:|
| COMBO | 0.3137 | 0.1705 | 0.1084 |
| a030 | 0.4200 | 0.2935 | 0.1627 |
| **a043** | **0.4837** | **0.3534** | **0.1997** |
| **R39R40_a025** | **0.4381** | **0.3083** | **0.1696** |
| **a043 − a025** | **+0.0456** | **+0.0451** | **+0.0301** |

#### edge_retention(↑)

| model | supra | mixed | sub |
|---|---:|---:|---:|
| COMBO | 0.8588 | 0.4538 | 0.1994 |
| a030 | 0.8956 | 0.5472 | 0.2314 |
| **a043** | **1.0091** | **0.6527** | **0.3115** |
| **R39R40_a025** | **0.9248** | **0.5728** | **0.2482** |
| **a043 − a025** | **+0.0843** | **+0.0799** | **+0.0633** |

#### PSNR(↑)

| model | supra | mixed | sub |
|---|---:|---:|---:|
| COMBO | 23.8362 | 19.3844 | 19.4480 |
| a030 | 26.1217 | 21.6386 | 20.8567 |
| **a043** | **27.9068** | **23.2680** | **21.8370** |
| **R39R40_a025** | **26.5900** | **22.0507** | **21.0984** |
| **a043 − a025 (dB)** | **+1.32** | **+1.22** | **+0.74** |

### 視覺化

`feature_width_scatter.png` 四宮格散布圖,x 軸是 GT median stroke width(log scale),y 軸分別是 shape_error_score、corner_retention、straight_edge_coverage、boundary_f_score。Rayleigh = 11.7 px 用虛線標出。

可以看到:

- 在 Rayleigh 左側(sub-Rayleigh)樣本量明顯少且 shape_error 較高,boundary_f_score 較低——符合物理上限預期。
- a043(紅)點分布大致在 a025(綠)之上(對 ↑ 指標)或之下(對 ↓ 指標),差距集中在 supra-Rayleigh 區段。

## 解讀

### 為什麼 a043 在 supra-Rayleigh 強很多、sub-Rayleigh 強得少

- supra-Rayleigh:PSF 模糊雖然 ill-posed 但可逆,訓練資料量決定模型能不能學會把模糊邊界鎖回正確位置。a043 用了 R40 micro_capacity_train(1300 對含 line/grid/large_region/texture/defect/mixed 五類顯微特徵),對 supra-Rayleigh 結構覆蓋好。a025 是 0.25 × a043 + 0.75 × a030 權重平均,a030 train 沒看過 R40 顯微特徵,所以 a025 supra-Rayleigh 表現相對軟。
- sub-Rayleigh:即使訓練資料完美,sub-Rayleigh 的高頻訊息物理上被砍掉,模型只能做 MMSE 意義下的最佳估計(平滑、圓弧化、低對比)。所以 a043 跟 a025 在這個區段差距小,因為兩者都受同一個物理上限約束。

### a043 在 sub-Rayleigh 的 straight_edge_coverage 反而退步

a043 退 1.91 pp 是個 signal:a043 對 sub-Rayleigh 區域用更銳的輸出嘗試還原細節,但因為訊息不在了,輸出的「銳化」變成 high-frequency noise——直邊上出現跳斷、波紋,反而被 straight_edge_coverage 抓到退步。a025 因為混了較柔的 a030,在 sub-Rayleigh 反而較穩。

這對 R46 corner-aware fine-tune 是重要提醒:**強推高頻在 sub-Rayleigh 會反噬**。

### 「直角變圓弧、三角形變一坨」這個 symptom 落在哪

- 三角形(R39 stage_01):從 sample 看,median stroke width 約 12 px(剛好在 Rayleigh 附近),sub_rayleigh_frac 約 50%——三角形整體在 mixed,尖端可能 sub、底邊可能 supra。
- 細線/格線(R40 stage_29):median 4 px,sub_rayleigh_frac 74%——絕大部分 sub-Rayleigh,fine-tune 改善空間小。
- 多邊形/大形狀(R39 stage_05/07):median 80-200 px,sub_rayleigh_frac < 5%——完全 supra,fine-tune 改善空間最大。

所以使用者抱怨的 symptom 分布:

| Symptom | 主要 class | fine-tune 空間 |
|---|---|---|
| 三角形變一坨(R39 stage_01) | mixed(尖端 sub、底邊 supra) | 中等(尖端救不了、底邊可推) |
| 直角變圓弧(R39 stage_03 / stage_05) | supra | 大 |
| 細線抹掉(R40 stage_29) | sub | 小 |
| 大區塊邊角(R40 stage_30) | supra | 大 |

## R46 升級判定

### 結論

**值得開 R46(以 a025 為起點做 corner-aware 微調),但 expected gain 要照 supra-Rayleigh 占比 deflate**。

### Expected gain 上限(假設 R46 完美達到 a043 在每個分桶的水準)

以 a043 vs a025 的分桶差距加權平均(weight = 樣本佔比 76.8% / 17.1% / 6.1%):

| 指標 | 加權期望改善 |
|---|---:|
| corner_retention | +0.0157 |
| straight_edge_coverage | +0.0212 |
| boundary_f_score | +0.0267 |
| HF retention | +0.0445 |
| edge retention | +0.0815 |
| PSNR | +1.28 dB |
| shape_error_score | −0.0125 |

實際 R46 fine-tune 要守 ring guard、用低 LR 跟短 epoch,**估計實際拿到上限 50 ~ 80%**:

| 指標 | 期望實際改善(50-80% cap) |
|---|---:|
| corner_retention | +0.008 ~ +0.013 |
| boundary_f_score | +0.013 ~ +0.021 |
| HF retention | +0.022 ~ +0.036 |
| PSNR | +0.64 ~ +1.02 dB |

### R46 設計建議

1. **資料配比偏向 supra-Rayleigh 樣本**:R40 micro 訓練包要強化 stage_30 / stage_32 / stage_33 的 supra 部分,而非 stage_29 lines/grid(已在 sub 區段、訓練 marginal)。
2. **corner-aware loss 強度溫和**:weight × 5(而非原本草案的 5-10),避免 a043 在 sub-Rayleigh 出現的 straight_edge 跳斷重現。
3. **加 sub-Rayleigh 平滑 penalty**(可選):對 GT 上 `sub_rayleigh_frac` 高的區域,壓抑輸出 local gradient 過尖,反向 enforce 模型「不要過度 hallucinate sub-Rayleigh 細節」。這是針對 sub 區段的 honest output 約束。
4. **驗證 metric 加 Rayleigh 分桶**:R46 完成後重跑這份診斷,看 fine-tune 後 supra delta 是否縮小、sub straight_edge 是否守住。

### 不要做的事

- 期望 sub-Rayleigh 細線 / 紋理 / 三角形尖端有大幅改善——物理上限在那。
- 用 R40 a043 train 大份比例混進去:這會把 a025 變回 a043,失去 a025 的三尺度 ring guard 平衡。
- 對 sub_rayleigh_frac > 50% 的樣本強行推高 corner-aware weight。

## 限制

1. **per-image 分桶,沒做 per-pixel 分析**:單張 mixed 影像內部 supra 區域跟 sub 區域是混雜的,本診斷以該影像 median stroke width 代表,可能 over-簡化。後續可以做 per-pixel 分析,把每張影像的 supra-pixel-only-corner 跟 sub-pixel-only-corner 分開算 retention。
2. **GT threshold 固定 50**:沒做 sensitivity sweep。R40 stage_31_micro_textures 內部灰階梯度多,threshold 對 stroke width 影響可能不可忽略。
3. **沒算 PSF 理論曲率對照**:對 GT 做物理 PSF convolution + 量輸出 corner 曲率半徑可以給「物理理論下限」絕對基準。本診斷用 a043 當實驗錨(假設 a043 在 R40 train 上充分學習,接近該分布下的訓練上限),這只是相對基準。
4. **Rayleigh 公式假設非相干 incoherent imaging + Airy PSF**:實際 PSF 是 fitted 2D PSF,可能跟 Airy 略有差異。11.7 px 是教科書估算,實際 effective cutoff 可能在 10 ~ 13 px 區間。

## 產物

| 檔案 | 內容 |
|---|---|
| `../rayleigh_diagnostic/per_pair_with_width.csv` | 1240 列 csv,既有指標 + sw_median_px / sw_p25_px / sw_p75_px / sw_max_px / sub_rayleigh_frac / rayleigh_class / n_fg_px / n_skel_px |
| `../rayleigh_diagnostic/aggregate_by_class.csv` | 16 列 (model × class) 的 mean / median / n 樞紐 |
| `../rayleigh_diagnostic/rayleigh_summary.md` | 機器產的指標 × 模型 × class 表格(本報告引用源) |
| `../rayleigh_diagnostic/feature_width_scatter.png` | 四宮格散布圖 |
| `Experiments/R39_ShapeGeneralization/scripts/rayleigh_diagnostic.py` | 主腳本 |

## 方法可重跑

```bash
cd D:/GMM_2_Final
python Experiments/R39_ShapeGeneralization/scripts/rayleigh_diagnostic.py \
    --rayleigh-px 11.7
```

可調 `--rayleigh-px` 做 sensitivity check(例如 9.0 / 11.7 / 14.0)。

本診斷不改 a025 既有 verdict;它回答的是「a025 邊角細節是否值得繼續推,以及怎麼推」這個策略問題,輸出結論是「值得開 R46,但 expected gain 要照 supra-Rayleigh 占比 deflate,且 corner-aware loss 強度要克制」。
