# 推理量化修復分析

**日期**: 2026-04-08
**修復內容**: `denormalize_to_dtype()` 中 `.astype(dtype)` 截斷改為 `np.rint()` 四捨五入
**檔案**: `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py` L434
**影響範圍**: 50% 的像素值 +1 grey level（從截斷變為四捨五入的自然結果）

## Bug 描述

```python
# 修復前（截斷）：
out = pred01 * 255
return np.clip(out, 0, 255).astype(np.uint8)  # 0.498*255=126.99 → 126

# 修復後（四捨五入）：
out = pred01 * 255
return np.clip(np.rint(out), 0, 255).astype(np.uint8)  # 0.498*255=126.99 → 127
```

## 外部 GMF 影響

### R33 p95

| 尺度 | 修復前 | 修復後 | 變化 | Outliers 舊→新 | 分析 |
|------|--------|--------|------|----------------|------|
| **0.8px** | 0.119049 | **0.117072** | **-1.7%** | 0→0 | 真正改善 |
| 0.08px | 0.086274 | **0.085633** | -0.7% | 0→0 | 真正改善 |
| 8px | 0.153343 | 0.171765 | +12.0% | **2→0** | 見下方分析 |

**R33 8px 的「退步」實為改善**：
- 修復前：Frame 51-52 step=-1.52（偏離 median -8.03 達 6.51 px）、Frame 52-53 step=-14.47（偏離 6.44 px）
- 這 2 幀是 catastrophic outlier → outlier removal 丟掉後報告 step_std=0.153（97 步）
- 修復後：0 個 outlier，所有 99 步在 [-8.34, -7.58] 窄範圍 → step_std=0.172（99 步）
- **數字上升但品質更好**——catastrophic 定位偏差被消除，不再需要 outlier removal

### R38v2

| 尺度 | 修復前 | 修復後 | 變化 | Outliers 舊→新 | 分析 |
|------|--------|--------|------|----------------|------|
| 0.8px | 0.134205 | 0.146742 | **+9.3%** | 0→0 | 真正退步 |
| 0.08px | 0.106457 | 0.109085 | +2.5% | 0→0 | 微幅退步 |
| **8px** | 0.143988 | **0.121984** | **-15.3%** | 0→0 | 大幅改善 |

**R38v2 0.8px 退步的根因**：R38v2 的 edge steepness 極高（+89% vs R30），陡峭邊緣在 uint8 量化時，+1 grey level 就能移動 edgel 位置。R33 的邊緣較柔（steepness -22%），對量化方式的敏感度更低。

## 結論

| 候選 | 量化修復影響 | 建議 |
|------|------------|------|
| R33 p95 | 0.8px/0.08px 微幅改善；8px outlier 消除 | **採用修復版** |
| R38v2 | 8px 大幅改善（-15%）；0.8px 退步（+9%） | **需權衡——8px 改善是否值得 0.8px 退步** |

量化修復在數學上更正確（四捨五入 vs 截斷），但對不同模型的 edgel detection 影響方向不同。這不是 bug 修復的問題——是 GMF 對 uint8 邊緣敏感度的特性。

## GMF 數據完整路徑

| 候選 | 版本 | 路徑 |
|------|------|------|
| R33 修復前 | `results/external_gmf/` | 原始 GMF scores |
| R33 修復後 | `results/external_gmf_quantfix/` | 量化修復後 GMF scores |
| R33 修復後重建 | `results/p95_recon_quantfix/` | 量化修復後 BMP |
| R38v2 修復前 | `R38v2SeqFixed/results/external_gmf/` | 原始 GMF scores |
| R38v2 修復後 | `R38v2SeqFixed/results/external_gmf_quantfix/` | 量化修復後 GMF scores |
| R38v2 修復後重建 | `R38v2SeqFixed/results/8px_gate_recon_quantfix/` | 量化修復後 BMP |
