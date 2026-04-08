# Internal vs External Step_std 偏差分析

**日期**: 2026-04-08
**發現**: Internal step_std 系統性高估 external GMF step_std，且偏差隨模型品質提升而擴大

## 觀測數據

| 候選 | Internal 0.8px | External 0.8px | 比率 (Int/Ext) | 高估幅度 |
|------|---------------|---------------|---------------|---------|
| R30 baseline | 0.205 | 0.168 | 1.22 | +22% |
| R33 p95 | 0.129 | 0.119 | 1.08 | +8% |
| R38v2 | 0.170 | 0.134 | 1.27 | +27% |
| **COMBO** | **0.178** | **0.132** | **1.35** | **+35%** |

**COMBO 的 internal 0.178 超過門檻 0.168，如果只看 internal 會被錯誤丟棄。
但 external 0.132 是三候選中第二好的。**

## 根因分析

### Circle Fit 的噪聲地板

Internal step_std 用 circle fit 的 `outer_fit_cy` 做 `np.diff → np.std`。
Circle fit 用 360 個離散角度的 least squares 擬合。

```
每幀圓心精度 ≈ residual_std / √(n_angles)
             ≈ 2.33 / √360
             ≈ 0.123 px

雙幀 step 精度 (RSS) ≈ 0.123 × √2 ≈ 0.174 px
```

**0.174 px 是 circle fit 的理論噪聲地板。**

COMBO 的 internal step_std = 0.178 ≈ 噪聲地板。
真實的 step 變異已經被量測噪聲完全淹沒——internal 看到的主要是自身的噪聲。

### GMF 的噪聲地板更低

GMF 用全環 template matching，有效取樣點遠多於 360——整個 annulus 區域的所有像素都參與定位。
噪聲地板遠低於 circle fit。

### 數學驗證

假設 internal 和 external 量測同一個真實 step 序列：

```
internal_std² = real_std² + σ_noise²
external_std² ≈ real_std²

σ_noise = √(0.178² - 0.132²) = 0.119 px
理論值 = 0.174 px（同一量級）
```

差異因為 circle fit 的噪聲不是純隨機——缺陷角度的槓桿效應使實際噪聲低於理論值。

### 為什麼偏差隨品質提升而擴大

R30: residual_std ≈ 2.6 → 噪聲地板 2.6/√360×√2 ≈ 0.194
COMBO: residual_std ≈ 2.3 → 噪聲地板 2.3/√360×√2 ≈ 0.171

噪聲地板隨 residual 下降而下降，但下降速度不夠快。
當 external step_std 降到 0.13 時，circle fit 的噪聲（0.17）仍然主導 internal，
導致 internal/external 比率越來越高。

## Step 分佈比較（COMBO 0.8px）

| 分位數 | Internal | External | Internal 更散 |
|--------|---------|---------|-------------|
| P10 | -1.012 | -0.940 | 是 |
| P25 | -0.911 | -0.898 | 是 |
| P50 | -0.805 | -0.802 | ≈ |
| P75 | -0.684 | -0.721 | 否（internal 更集中） |
| P90 | -0.624 | -0.648 | 否 |
| Range | 1.050 | 0.732 | **1.43x 更寬** |

Internal 的分佈在尾部（P10、P90 以外）明顯更散——這就是 circle fit 噪聲的表現。

## 影響

1. **Internal step_std 不再適合作為候選篩選硬門檻**（在 residual < 2.5 的精度範圍）
2. **ESTIMATOR_POLICY 的 internal gate 需要更新**
3. **center_err Pearson r=0.54 的有效範圍已超出**（那是 R26-R32 的舊樣本）

## 改善方向（路線 A：改善量測方法）

### A1：增加角度取樣

360 → 720：噪聲地板降 √2 ≈ 0.123 px
360 → 1080：噪聲地板降 √3 ≈ 0.100 px

需修改：`AnalysisLab/r26/single_image/scripts/run_single_image_analysis.py`
的 `extract_radial_edge_candidates()` 和 `summarize_circle_fits()`

### A2：加權 circle fit

在 circle fit 中對缺陷角度降權（persistent hotspot angles weight → 0.3）。
不改訓練，只改量測端。

需修改：`summarize_circle_fits()` 中的 least squares 權重

### A3：全環 template matching proxy

在 internal 用類似 GMF 的 normalized cross-correlation：
1. 取每幀的 annulus ring 區域
2. 用 NCC 對齊相鄰幀
3. 從對齊結果取 step

這最接近 GMF 的行為，但實作最複雜。

### 建議順序

A1 最簡單（改一個 n_angles 參數），A2 次之，A3 最複雜。
先做 A1 看噪聲地板是否下降到可接受範圍，再決定是否需要 A2/A3。

## A1 實施結果（2026-04-08）

已將 sequence analysis 的 `extract_radial_edge_candidates` n_angles 從 360 改為 720。
四個候選全部重跑驗證：

### 0.8px Internal/External 比率

| 候選 | 360/Ext | 720/Ext | 改善 |
|------|---------|---------|------|
| R30 | 1.221 | **1.035** | 高估 22% → 3.5% |
| R33 | 1.083 | **1.045** | 高估 8% → 4.5% |
| R38v2 | 1.268 | **1.222** | 高估 27% → 22% |
| COMBO | 1.349 | **1.147** | 高估 35% → 15% |

### 完整數據

| 候選 | 尺度 | 360-angle | 720-angle | External | 720/Ext |
|------|------|----------|----------|---------|---------|
| R30 | 0.8px | 0.205 | 0.174 | 0.168 | 1.035 |
| R30 | 0.08px | 0.162 | 0.139 | 0.158 | 0.880 |
| R30 | 8px | 0.199 | 0.178 | 0.205 | 0.866 |
| R33 | 0.8px | 0.129 | 0.124 | 0.119 | 1.045 |
| R33 | 0.08px | 0.115 | 0.109 | 0.086 | 1.266 |
| R33 | 8px | 0.174 | 0.166 | 0.153 | 1.081 |
| R38v2 | 0.8px | 0.170 | 0.164 | 0.134 | 1.222 |
| R38v2 | 0.08px | 0.156 | 0.145 | 0.106 | 1.365 |
| R38v2 | 8px | 0.139 | 0.132 | 0.144 | 0.918 |
| COMBO | 0.8px | 0.178 | 0.151 | 0.132 | 1.147 |
| COMBO | 0.08px | 0.132 | 0.119 | 0.100 | 1.186 |
| COMBO | 8px | 0.140 | 0.139 | 0.155 | 0.899 |

### 結論

- **A1（720 角度）有效降低 circle-fit 噪聲**，特別對 0.8px 主戰場
- R30 的 720/Ext 比率 1.035 幾乎完美——代表 720 角度在 R30 精度範圍足夠
- COMBO 從 1.35 降到 1.15——仍有 15% 高估，可能需要 A2（加權 fit）進一步改善
- **COMBO 的 720-angle internal 0.151 < 0.168 門檻——不會再被錯誤丟棄**
- R38v2 仍高估 22%——其 residual_std 較高（3.15），噪聲來源不只是角度不足
