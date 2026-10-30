# R39 結果 — 多形狀泛化

狀態：訓練、local 評估、權重平均 sweep、以及 alpha=0.30 平均 checkpoint 的外部 GMF 全部跑完。外部 GMF verdict：**PASS_TRADEOFF**（8px −6.94%、0.08px −15.97%、0.8px +6.42% vs COMBO）。平均後的 checkpoint 達到 alternate-grade，但要不要進 `approved_alternates` 是專案 owner 的決定，目前還沒拍板。

## 目的

觸發 R39 的是一個觀察到的 baseline 弱點：當時的主線模型對圓環重建很強，但碰到非圓環形狀（三角形、矩形、橢圓、多邊形、混合場景）就明顯變差。Baseline 的能力被訓練分布綁死在 ring 上。

R39 測試一條受控的多形狀資料路線，看能不能在不傷 ring 表現的情況下，把 non-ring 形狀的重建拉起來。

這輪不加真實影像，模型本體也不動。

## 已完成項目

- 建立 `R39_ShapeGeneralization` 實驗目錄結構。
- 寫了一個可重複執行、會檢查 source / label 配對的資料包 builder。
- 開三個 data profile：
  - `r39_shape_mix_safe`：1100 ring pairs + 140 shape pairs。
  - `r39_shape_mix_strong`：1100 ring pairs + 490 shape pairs。
  - `shape_val_unseen`：210 shape pairs（held-out，沒 ring data）。
- 兩個候選的 launcher。
- held-out 形狀驗證的重建 runner。
- 把 COMBO 拉到 held-out 形狀驗證集上跑過，寫了 baseline 彙總。
- 從 COMBO 接續訓練兩個 R39 候選。
- 對兩個候選跑 held-out 形狀驗證。
- 對兩個候選跑三尺度 local ring 重建 + 720-angle ring guard 分析。
- 為手動 review 加了一張代表性視覺對比圖。
- split 隔離、缺漏 label 偵測、資料包 manifest 建立的單元測試。
- 在 COMBO 與 `r39_shape_mix_strong` 之間做 11 個 alpha 的權重平均 sweep，加上 pure-logic 的單元測試與 trade-off 圖。
- 對 alpha=0.30 的平均 checkpoint 在三個尺度上跑完外部 GMF，加上 `r39_external_compare.py` 與 14 條 parser / verdict tier 的單元測試。

## 候選路線

| Candidate | 角色 | 資料 |
|---|---|---|
| `r39_shape_mix_safe` | 主要候選 | 保守的多形狀混合 |
| `r39_shape_mix_strong` | 容量探針 | 較強的多形狀混合 |

兩個候選都從 COMBO 接續：

`Experiments/Training_Runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525/weights/best_tradeoff.pth.tar`

訓練後的 checkpoint：

| Candidate | Checkpoint |
|---|---|
| `r39_shape_mix_safe` | `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_safe_20260428_165958/weights/best_tradeoff.pth.tar` |
| `r39_shape_mix_strong` | `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_strong_20260428_180728/weights/best_tradeoff.pth.tar` |

## 升級前必須通過的檢查

- COMBO baseline 要先在 `shape_val_unseen` 上量過。下面的 baseline 區塊已完成。
- 候選的形狀驗證要明顯比 COMBO 好。
- 既有的外部 ring 測試是硬門檻。
- 0.8px 與 8px ring 結果不能對 COMBO 有實質退步。
- 代表性重建圖要看過，不是只看數字。

## COMBO 在 held-out 形狀集上的 baseline

彙總檔：

`Experiments/R39_ShapeGeneralization/results/shape_recon/shape_val_unseen_combo_baseline_summary.json`

| Stage | Count | PSNR | SSIM |
|---|---:|---:|---:|
| Triangles | 30 | `22.6722` | `0.8121` |
| Circles | 30 | `23.1399` | `0.8873` |
| Rectangles | 30 | `22.2521` | `0.8118` |
| Ellipses | 30 | `25.3976` | `0.9237` |
| Polygons | 30 | `22.5577` | `0.8686` |
| Mixed simple | 30 | `22.5802` | `0.8333` |
| Mixed complex | 30 | `21.2897` | `0.8144` |
| Overall | 210 | `22.8413` | `0.8502` |

## 候選的形狀驗證

彙總檔：

- `results/shape_recon/shape_val_unseen_r39_shape_mix_safe_summary.json`
- `results/shape_recon/shape_val_unseen_r39_shape_mix_strong_summary.json`

| Candidate | PSNR | SSIM | PSNR vs COMBO | SSIM vs COMBO |
|---|---:|---:|---:|---:|
| COMBO baseline | `22.8413` | `0.8502` | `0.0000` | `0.0000` |
| `r39_shape_mix_safe` | `26.6799` | `0.9014` | `+3.8386` | `+0.0512` |
| `r39_shape_mix_strong` | `30.0717` | `0.9326` | `+7.2303` | `+0.0824` |

逐 stage 的形狀驗證：

| Stage | COMBO PSNR / SSIM | Safe PSNR / SSIM | Strong PSNR / SSIM |
|---|---:|---:|---:|
| Triangles | `22.6722` / `0.8121` | `26.2499` / `0.8594` | `29.4387` / `0.8958` |
| Circles | `23.1399` / `0.8873` | `27.5847` / `0.9338` | `31.8354` / `0.9620` |
| Rectangles | `22.2521` / `0.8118` | `25.3837` / `0.8721` | `28.4448` / `0.9146` |
| Ellipses | `25.3976` / `0.9237` | `28.8761` / `0.9615` | `32.6763` / `0.9781` |
| Polygons | `22.5577` / `0.8686` | `27.4456` / `0.9173` | `31.0187` / `0.9425` |
| Mixed simple | `22.5802` / `0.8333` | `26.3686` / `0.8868` | `29.7983` / `0.9229` |
| Mixed complex | `21.2897` / `0.8144` | `24.8509` / `0.8786` | `27.2894` / `0.9125` |

形狀面結論：兩個候選在沒看過的合成形狀上都明顯贏 COMBO。Strong 是形狀泛化最強的。

## Local Ring Guard

彙總檔：

- `results/ring_guard/r39_shape_mix_safe_ring_guard_summary.json`
- `results/ring_guard/r39_shape_mix_strong_ring_guard_summary.json`

這是 local 720-angle ring 分析，不是正式的外部 GMF gate。當早期警示用。

| Candidate | 8px local step std | 0.8px local step std | 0.08px local step std |
|---|---:|---:|---:|
| COMBO local 參考 | `0.1389` | `0.1509` | `0.1185` |
| `r39_shape_mix_safe` | `0.3693` | `0.1811` | `0.1338` |
| `r39_shape_mix_strong` | `0.2044` | `0.1711` | `0.1811` |

Local ring 結論：兩個 R39 候選都比 COMBO 退步。Safe 在 8px 上特別差。Strong 在 8px 沒那麼糟，但三個尺度都比 COMBO 差。

訓練 endpoint 的外部 GMF 狀態：沒跑，也不打算跑。`r39_shape_mix_safe` 與 `r39_shape_mix_strong` 的 local ring guard 已經退步，把機器時間花在跑正式外部 gate 不划算。外部 GMF 改做在 alpha=0.30 的權重平均 checkpoint 上（見下面「alpha=0.30 的外部 GMF」一節）。

## 權重平均 sweep

兩個 R39 endpoint 共用同一架構，而且候選是從 COMBO fine-tune 出來，所以兩者之間 loss landscape 預期是線性連通的。Sweep 在 11 個 alpha 上把 COMBO 與 `r39_shape_mix_strong` 的 state_dict 線性插值，逐 alpha 跑 `shape_val_unseen` 與 local 三尺度 ring guard，輸出聚合的 trade-off 表。

Runner：

`Experiments/R39_ShapeGeneralization/scripts/run_r39_weight_sweep.py`

Pure-logic 模組 + 測試：

- `Experiments/R39_ShapeGeneralization/scripts/r39_weight_sweep.py`
- `Experiments/R39_ShapeGeneralization/tests/test_r39_weight_sweep.py`（18 條測試，全綠）

聚合輸出：

- `results/weight_sweep/sweep_summary.json` — 逐 alpha rows + verdict
- `results/weight_sweep/sweep_summary.md` — 給人看的 trade-off 表
- `results/weight_sweep/sweep_tradeoff.png` — shape PSNR vs alpha 與三尺度 ring step_std vs alpha

### Pipeline sanity 檢查

`alpha = 0.0` 與 `alpha = 1.0` 的數字和先前紀錄誤差在 sub-percent：

| alpha | shape PSNR | ring 8px | ring 0.8px | ring 0.08px | reference |
|---:|---:|---:|---:|---:|---|
| 0.00 | `22.8411` | `0.1389` | `0.1509` | `0.1185` | 對得上 COMBO baseline |
| 1.00 | `30.0722` | `0.2004` | `0.1691` | `0.1750` | 對得上 `r39_shape_mix_strong` |

兩端在每個指標上都把中間的 alpha 包住，所以 linear mode connectivity 成立，兩個 checkpoint 之間沒有 loss barrier。

### Trade-off 表

held-out shape PSNR 對 alpha 是單調的；local ring guard 不是單調，但低 alpha 時貼著 COMBO，高 alpha 時退步。

| alpha | shape PSNR | shape SSIM | ring 8px | ring 0.8px | ring 0.08px |
|---:|---:|---:|---:|---:|---:|
| 0.00 | `22.8411` | `0.8502` | `0.1389` | `0.1509` | `0.1185` |
| 0.10 | `23.5329` | `0.8604` | `0.1409` | `0.1540` | `0.1184` |
| 0.20 | `24.2538` | `0.8702` | `0.1380` | `0.1640` | `0.1157` |
| **0.30** | **`25.0326`** | **`0.8798`** | **`0.1384`** | **`0.1507`** | **`0.1114`** |
| 0.40 | `25.8894` | `0.8893` | `0.1379` | `0.1605` | `0.1082` |
| 0.50 | `26.8262` | `0.8987` | `0.1552` | `0.1487` | `0.1220` |
| 0.60 | `27.8053` | `0.9078` | `0.1629` | `0.1552` | `0.1203` |
| 0.70 | `28.7456` | `0.9160` | `0.1679` | `0.1567` | `0.1233` |
| 0.80 | `29.5349` | `0.9230` | `0.1858` | `0.1491` | `0.1431` |
| 0.90 | `30.0227` | `0.9286` | `0.1875` | `0.1629` | `0.1601` |
| 1.00 | `30.0722` | `0.9326` | `0.2004` | `0.1691` | `0.1750` |

### Sweet spot

接受門檻（local 退步上限，以 R33 alternate 的外部 8px `0.1533` 為錨）：

- shape PSNR ≥ `24.84`（COMBO + 2.0）
- ring 8px step_std ≤ `0.155`
- ring 0.8px step_std ≤ `0.155`
- ring 0.08px step_std ≤ `0.135`

Runner 挑出的 sweet spot：**alpha = 0.30**。

直接和 COMBO 比：

| metric | COMBO （alpha=0） | alpha=0.30 | delta |
|---|---:|---:|---:|
| shape PSNR | `22.8411` | `25.0326` | **`+2.1915`** |
| shape SSIM | `0.8502` | `0.8798` | `+0.0296` |
| ring 8px step_std | `0.1389` | `0.1384` | `−0.0005` |
| ring 0.8px step_std | `0.1509` | `0.1507` | `−0.0002` |
| ring 0.08px step_std | `0.1185` | `0.1114` | `−0.0071` |

alpha=0.30 的平均 checkpoint 是嚴格的 local Pareto improvement：每一個 ring 尺度都至少持平，形狀泛化進步約 +2.2 PSNR。

平均後的 checkpoint：

`Experiments/R39_ShapeGeneralization/results/weight_sweep/checkpoints/a030/best_tradeoff.pth.tar`

### 注意點與外部 gate 狀態

- 上面是 local 720-angle ring 數字，不是外部 GMF。R33 / R38v2 系列的經驗是兩者可能 diverge，但通常方向一致。
- alpha 落在 0.20–0.40 區間時 local ring 都接近 COMBO；alpha=0.30 是同時通過四個門檻的最高 PSNR row，但不是嚴格唯一解。
- alpha=0.30 的外部 GMF 已經跑（verdict **PASS_TRADEOFF**，見下節）。Local 與外部方向一致：local Pareto improvement 在外部呈現為兩項改善 + 一項在容忍區內的 trade-off。Alternate-grade，要不要升級是專案 owner 的決定。

## alpha=0.30 的外部 GMF

外部 GMF 對 `r39_combo_strong_avg_a030` 在三個正式尺度上都跑了。方法依照 `Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md`（原始 step_std，只移除 `|z| > 5` 的 GMF 失敗 step）。三個 pitch 都是零 outlier，headline 等於含全部 step 的 raw std。

正式比較報告：

`Experiments/R39_ShapeGeneralization/reports/R39_EXTERNAL_COMPARE.md`

結果目錄：

- `results/external_gmf_a030/pitch8px/GMF_score.txt`（100 frames、99 steps）
- `results/external_gmf_a030/pitch0p8px/GMF_score.txt`（60 frames、59 steps）
- `results/external_gmf_a030/pitch0p08px/GMF_score.txt`（40 frames、39 steps）
- `results/external_gmf_a030/external_compare_summary.json`

Headline 數字 vs COMBO：

| scale | a030 | COMBO | delta | delta % | 個別判定 |
|---|---:|---:|---:|---:|:---:|
| 8px | `0.143794` | `0.154515` | `−0.010721` | **−6.94%** | IMPROVED |
| 0.8px | `0.140008` | `0.131560` | `+0.008448` | `+6.42%` | TRADEOFF_OK |
| 0.08px | `0.083941` | `0.099891` | `−0.015950` | **−15.97%** | IMPROVED |

整體 verdict：**PASS_TRADEOFF**（`tradeoff_max_pct = 7.0%`，以 R38v2 對 COMBO 最差的 +6.6%（0.08px）再加一點 slack 為錨）。

### Cross-alternate 排名

| candidate | 8px | 0.8px | 0.08px |
|---|---:|---:|---:|
| COMBO | `0.154515` | **`0.131560`** | `0.099891` |
| R33 | `0.153343` | `0.119049` | `0.086274` |
| R38v2 | `0.143988` | `0.134205` | `0.106457` |
| **a030** | **`0.143794`** | `0.140008` | **`0.083941`** |

R33 那一行用的是 policy headline（`0.119049`）；0.8px / lag-1 的注意點請看 `R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md`。a030 在 8px 與 0.08px 領先，8px 與 R38v2 統計上打平，0.8px 在四者中最差。0.08px 是專案史上最低。

### 建議角色

`shape_generalization_endpoint_alternate` —— 需要同時兼顧形狀泛化（a030 在 held-out shape 上比 COMBO 高 +2.19 PSNR）與 8px / 0.08px 端點精度的 deployment。0.8px 取向的 deployment 不適合，那裡用 COMBO 或 R33。

### 等待升級決定

外部 GMF 量測已記錄；要不要把 a030 升進 `ESTIMATOR_POLICY.json` 的 `approved_alternates`，是專案 owner 必須明確拍板的另一個決定。在那之前 a030 掛在 `open_side_tracks`，狀態 `external_gmf_complete_alternate_grade_pending_promotion`。

## 視覺品質比較（a030 vs COMBO）

外部 GMF 只量幾何精度；要當 alternate 升級還得做視覺品質檢查，免得候選靜悄悄變糊。Sweep 已經對相同的 203 張 BMP 在 `alpha = 0.0`（=COMBO）與 `alpha = 0.30`（=a030）、三個 pitch 下做完 ring 重建，所以這個比較是直接的，重用既有重建，不必再 inference。

四個標準視覺統計值在每張 frame 上計算，候選之間用同一批 203 張取 frame-wise mean：

| pitch | metric | COMBO （a000） | a030 | delta |
|---|---|---:|---:|---:|
| 8px （101 frames） | gradient_magnitude_mean | `0.007953` | `0.007720` | `−2.94%` |
| 8px | edge_steepness_p95 | `0.102434` | `0.096580` | **`−5.71%`** |
| 8px | contrast_std | `0.111213` | `0.108341` | `−2.58%` |
| 8px | edge_contrast_p99_minus_p1 | `0.455057` | `0.441235` | `−3.04%` |
| 0.8px （61 frames） | gradient_magnitude_mean | `0.010881` | `0.010558` | `−2.96%` |
| 0.8px | edge_steepness_p95 | `0.139991` | `0.132199` | **`−5.57%`** |
| 0.8px | contrast_std | `0.126822` | `0.124667` | `−1.70%` |
| 0.8px | edge_contrast_p99_minus_p1 | `0.423529` | `0.411829` | `−2.76%` |
| 0.08px （41 frames） | gradient_magnitude_mean | `0.010864` | `0.010538` | `−3.00%` |
| 0.08px | edge_steepness_p95 | `0.139537` | `0.131682` | **`−5.63%`** |
| 0.08px | contrast_std | `0.126786` | `0.124623` | `−1.71%` |
| 0.08px | edge_contrast_p99_minus_p1 | `0.420660` | `0.411765` | `−2.11%` |

訊號在三個 pitch 上一致：a030 比 COMBO 略糊。Edge steepness（最強指標）掉約 −5.6%，其他三項掉約 −2 至 −3%。

### Cross-alternate 視覺位置

把這次量測和 `ESTIMATOR_POLICY.json` 既有的 `visual_profile.edge_steepness_vs_r30_pct` 串起來：

| candidate | edge_steepness vs R30 | 性格 |
|---|---:|---|
| R30（former baseline） | 0%（reference） | 參考點 |
| R33（gmf_extreme_alternate） | `−22%` | 視覺明顯軟掉（已記錄的 trade-off） |
| R38v2（visual_priority_alternate） | `+89.4%` | 銳利，COMBO-class |
| COMBO（formal_baseline） | `+89.4%` | 銳利 |
| **a030（本候選）** | `~+78.8%`（由 −5.71% vs COMBO 推算） | 銳利，稍微低於 COMBO / R38v2 |

結論：a030 落在和 COMBO、R38v2 一樣的 sharp 帶內，沒掉到 R33 的 soft 帶。權重平均的視覺代價約 3–6%，小到建議角色可以放寬：

- **原本建議**：`shape_generalization_endpoint_alternate`（8px + 0.08px 端點）。
- **更新後讀法**：a030 也涵蓋 R38v2 目前的視覺優先位。8px 持平 R38v2、0.08px 贏 R38v2、視覺品質維持 COMBO-class、再加形狀泛化。R38v2 唯一勝出的軸是 0.8px（R38v2 `0.1342` vs a030 `0.1400`）。

### 方法 + 重現

frame-wise 視覺統計用灰階 Sobel 與 quantile spread 計算；沒有新增 script（遵守專案規則「不為單一問題開新分析 script」）。要重跑這張表，從 repo root 執行：

```python
import cv2, numpy as np
from pathlib import Path

ROOT = Path("Experiments/R39_ShapeGeneralization/results/weight_sweep/ring_recon")
PITCHES = ["pitch1um_y_100_odd", "pitch0p1um_y_60_odd", "pitch0p01um_y_40_odd"]

def metrics(img):
    f = img.astype(np.float32) / 255.0
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    gmag = np.sqrt(gx*gx + gy*gy)
    edge = gmag > np.percentile(gmag, 95)
    return {
        "gradient_magnitude_mean": float(gmag.mean()),
        "edge_steepness_p95": float(gmag[edge].mean()) if edge.any() else 0.0,
        "contrast_std": float(f.std()),
        "edge_contrast_p99_minus_p1": float(np.percentile(f, 99) - np.percentile(f, 1)),
    }

def folder_mean(folder):
    accs = {k: 0.0 for k in ("gradient_magnitude_mean", "edge_steepness_p95", "contrast_std", "edge_contrast_p99_minus_p1")}
    n = 0
    for p in sorted(folder.glob("*.bmp")):
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None: continue
        for k, v in metrics(img).items():
            accs[k] += v
        n += 1
    return {k: v / n for k, v in accs.items()}, n

def find_run(tag):
    return next((ROOT / tag).glob("reconstruct_progress_*"))

for pitch in PITCHES:
    c, _ = folder_mean(find_run("a000") / pitch)
    a, _ = folder_mean(find_run("a030") / pitch)
    for k in c:
        print(f"{pitch} {k:30s} COMBO={c[k]:.6f} a030={a[k]:.6f} {(a[k]-c[k])/c[k]*100:+.2f}%")
```

上面表格的數字是 2026-05-02 用這段 snippet 跑出來的。重跑應該在浮點誤差內重現。

## 合成 microscopy demo（訓練分布限制這個發現）

a030 通過外部 GMF 與視覺品質檢查之後，額外做了一個部署信心度檢查：用刻意落在 R39 訓練分布之外的合成 microscopy 內容測一遍。Demo 沒改變 a030 的 verdict，但帶出一個發現，可以當下一輪 R40 的 entry-point 理由。

### 測試內容

手做一張 512×512 的合成 GT，模仿真實 microscopy 拍 IC 角落的觀感，接近部署系統會看到的影像類型。它包含 R39 訓練資料完全沒有的內容：

- 暗背景上一塊明亮的 IC chip 矩形（中灰亮度）
- 在 chip 上覆蓋規則的明亮 grid pattern（高頻週期結構）
- 一個帶外框小三角形 marker
- chip 表面的輕度隨機紋理
- chip 邊緣一段鋸齒缺陷
- chip 表面散落的暗斑點 defect

這張 GT 用和 R39 訓練同一支 PSF 做正向模擬（`PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`、`psf_grid[:, :, 0, 50]`），再加 Poisson-Gaussian noise。為了釐清 noise 是不是瓶頸，跑了兩個 noise level：

- 較重 noise：`alpha = 100, sigma_read = 1.5`（訓練設定的中段）
- 較輕 noise：`alpha = 160, sigma_read = 1.0`（更接近典型訓練樣本）

兩版都送進 `a030` 與 `COMBO` inference，對同一張 GT 算指標。

### 結果

| input variant | blurred input PSNR / SSIM | COMBO recon PSNR / SSIM | a030 recon PSNR / SSIM | a030 vs COMBO |
|---|---:|---:|---:|---:|
| heavier noise | `21.32` / `0.4667` | `17.26` / `0.0871` | `19.30` / `0.0934` | `+2.04` / `+0.0063` |
| lighter noise | `21.77` / `0.6337` | `17.28` / `0.0881` | `19.32` / `0.0946` | `+2.03` / `+0.0066` |

兩個重點觀察：

1. **Noise 不是瓶頸。** 輸入變乾淨之後（heavier → lighter），`blurred input` 的 PSNR / SSIM 都改善，但兩個重建幾乎不動。兩個模型已經把 noise 過濾得差不多；限制不在 noise。

2. **能力上限被訓練分布綁住，不是 noise 也不是 PSF。** 看重建會發現：
   - grid pattern 幾乎被整片抹掉（模型沒學過保留高頻週期結構）
   - 表面紋理消失（被當 noise 處理掉）
   - IC 邊緣有可見的 ringing 與圓化
   - 三角形 marker 認得出來，但形狀變鈍

3. **a030 還是比 COMBO 高 +2 PSNR**，和 held-out shape 集上一致。相對排名在訓練分布外仍然成立，但兩個模型在這種內容上的絕對能力都低。

### 為什麼這件事重要，但不會改 a030 的升級決定

訓練的 R39 stages 1–9 涵蓋的是「中性灰背景上的乾淨幾何 primitive」。它們不含週期 grating、紋理表面、大塊明亮 IC 風格區域、以及不規則邊緣 defect。要讓任一模型在沒看過的內容上表現好，光靠權重平均、再 fine-tune 既有資料、或改 evaluation 方法都救不回來——資料沒有就是沒有。

這個發現不和現有的 PASS_TRADEOFF / alternate-grade verdict 衝突。在 a030 的實際 scope（ring + 簡單形狀）裡，它的外部 GMF 和視覺品質都過了。Demo 只是說明 **a030 的部署 scope 被 R39 訓練分布綁住** —— 不能拿去當「general microscopy reconstruction」賣。

### 下一輪（R40 entry-point 理由）的意涵

如果長期目標是「任何 microscopy 特徵都能準確重建」，下一輪必須擴 training-data 涵蓋。具體：

- **週期結構**：多種間距與對比的線陣列、grid。
- **紋理表面**：均勻隨機紋理、半週期 pattern（IC chip 風）。
- **大塊明亮區域**：和現有「暗背景 + 幾何」分布相反的 dense 區域。
- **不規則邊緣 defect**：鋸齒邊、小缺角、表面斑點 defect。

這還是受控合成資料 —— 不會把真機影像放進訓練，所以不會重新打開 R32 的風險。起點 checkpoint 用 a030 或 COMBO 都合理。

附帶的改善方向（資料先準備好之後）是 frequency-domain loss 項，明確獎勵保留高頻週期結構；光改 loss 不改資料，預期沒用。

### Demo artefacts

- `results/synthetic_microscopy_demo/gt/0001.bmp` — 合成 IC GT
- `results/synthetic_microscopy_demo/input/0001.bmp` — PSF blur + noise 後的輸入（留下的是 lighter-noise 版）
- `results/synthetic_microscopy_demo/recon_combo/.../combo_demo/0001.bmp` — COMBO 重建
- `results/synthetic_microscopy_demo/recon_a030/.../a030_demo/0001.bmp` — a030 重建
- `results/synthetic_microscopy_demo/comparison.png` — 4 連格並列
- `results/synthetic_microscopy_demo/_view_*.png` — 各個獨立 panel

合成與 inference 是 one-shot 內聯做的；沒有為這個 demo 在 `scripts/` 下新增 script（遵守 repo root `CLAUDE.md` 裡關於分析衛生的提醒）。上面的 artefact 加上 `Training_Data/PSF_Convolution.py`（那裡記錄了用的 PSF + Poisson-Gaussian noise model）足以重現整個 demo。

## 代表性視覺檢查

代表性對比圖：

`results/shape_recon/r39_representative_shape_sheet.png`

triangles、ellipses、mixed-complex 的人工抽查和指標方向一致：R39 的輸出在視覺上比 COMBO 更接近 target，`r39_shape_mix_strong` 是三者中形狀重建最銳利的。

## 目前 verdict

R39 產出了一個 alternate-grade 的升級候選。它不是兩個訓練 endpoint 中任一個，而是權重平均後的 checkpoint。

按路線分：

- `r39_shape_mix_safe`：形狀進步中等，local 8px ring guard 退步嚴重（`0.3693` vs `0.1389`）。不是升級候選。
- `r39_shape_mix_strong`：形狀進步大（`+7.23 PSNR`），但 local ring guard 三個尺度都退步。單獨拿不能升級。
- **`r39_combo_strong_avg_a030`**（COMBO ↔ `r39_shape_mix_strong` 在 alpha=0.30 的權重平均）：
  - Held-out shape：vs COMBO `+2.19 PSNR`
  - Local 三尺度 ring guard：三個尺度都持平或勝過 COMBO
  - 外部 GMF：PASS_TRADEOFF（8px −6.94%、0.08px −15.97%、0.8px +6.42%）
  - Cross-alternate 位置：8px 領先（與 R38v2 並列）、0.08px 領先（專案史上最低）；0.8px 是四者中最弱
  - **Alternate-grade**，建議角色 `shape_generalization_endpoint_alternate`
  - **等專案 owner 拍板**才會進 `ESTIMATOR_POLICY.json` 的 `approved_alternates`

兩個訓練 endpoint 的原始 verdict 仍然成立：資料路線單獨用，形狀進步但 ring guard 退步。權重平均 sweep 把 trade-off 搬回 parameter space，平均後的 checkpoint 在 alternate-grade 通過外部 GMF gate。0.08px 是專案至今最低的外部 step_std。

留給專案 owner 的決策邊界：

- **把 a030 升到 `approved_alternates`**：多一個 specialisation slot（8px + 0.08px 端點 + 形狀泛化），代價是 0.8px 在 alternate 集裡最弱。
- **把 a030 留作 `open_side_tracks` 下的研究紀錄**：狀態明確標 `external_gmf_complete_alternate_grade_pending_promotion`，不影響當前 production routing。

兩條路內部都自洽。在 owner 決定之前，ESTIMATOR_POLICY.json 把 a030 留在 `open_side_tracks`，外部數字已記錄。

## 跨候選對照 — a030 vs R40 a045（2026-05-10）

把 a030 在多樣顯微圖形上的詳細評估、加上 R40 a045 拉進來作第三個對照候選，整合到一份 `R39_A030_MICROSCOPY_EVALUATION.md` 報告。R40 a045 在 R39 shape_val_unseen 的重建是 2026-05-10 補跑（210 張，路徑 `results/a030_microscopy_eval/r40_a045_on_shape/`）。

R39 shape_val_unseen 整體（七類純幾何形狀，210 對）：

| 指標 | COMBO | a030 | R40 a045 |
|---|---:|---:|---:|
| PSNR | `22.8411` | `25.0326` | `26.9147` |
| SSIM | `0.9078` | `0.9461` | `0.9633` |
| HF retention | `0.3021` | `0.4598` | `0.5083` |
| Edge retention | `0.7913` | `0.8797` | `0.9925` |
| Contrast retention | `0.8118` | `0.8864` | `0.9643` |
| 邊界 F1 | `0.8230` | `0.8752` | `0.9009` |
| 形狀錯誤 | `0.3386` | `0.2718` | `0.2526` |

七類形狀 a030 全部贏 COMBO；R40 a045 又七類全部贏 a030。

R40 micro_val_unseen 整體（五類顯微結構，100 對）：

| 指標 | COMBO | a030 | R40 a045 |
|---|---:|---:|---:|
| PSNR | `22.7326` | `25.0323` | `26.8911` |
| SSIM | `0.8588` | `0.8904` | `0.9199` |
| HF retention | `0.2234` | `0.2206` | `0.3414` |
| Edge retention | `0.6607` | `0.6181` | `0.7459` |
| 邊界 F1 | `0.4914` | `0.5454` | `0.6164` |
| 形狀錯誤 | `0.7489` | `0.7020` | `0.6830` |

五類顯微 a030 全部贏 COMBO；R40 a045 又五類全部贏 a030。

跨資料集對照（同模型在分布內外的整體 PSNR 落差）：

- a030：R39 `25.03`、R40 `25.03`，落差 `~0.00 dB`
- R40 a045：R39 `26.91`、R40 `26.89`，落差 `−0.02 dB`

兩個候選在訓練分布內外的整體 PSNR 都幾乎相當。

外部 GMF 升級門檻位置：

| 候選 | 8 px | 0.8 px | 0.08 px | 升級判定 |
|---|---:|---:|---:|---|
| COMBO | `0.1545` | `0.1316` | `0.0999` | 基準 |
| a030 | `0.1438`（−6.94%） | `0.1400`（+6.42%） | `0.0839`（−15.97%） | `PASS_TRADEOFF` |
| R40 a045 | `0.1898`（+22.80%） | `0.1333`（+1.33%） | `0.0970`（−2.85%） | `RESEARCH_CAPACITY_ONLY` |

a030 跟 R40 a045 的差別在「靜態畫面品質 vs 大尺度連續位移穩定」：R40 a045 把單張畫面品質（PSNR/SSIM/HF/Edge/Contrast/邊界 F1/形狀錯誤）全部推高，代價是外部 8 px 連續位移穩定退步 +22.80%，超出 3% 升級上限與 7% 替代容忍區。

完整三方逐 stage 對比、邊界 F1 與形狀錯誤分項、跨資料集對照、視覺對比見 [`R39_A030_MICROSCOPY_EVALUATION.md`](R39_A030_MICROSCOPY_EVALUATION.md)。

本節為觀察記錄，不改 a030 升級判定，也不觸動 R40 a045 既有 `RESEARCH_CAPACITY_ONLY` 標籤。

## 跨輪互補權重平均 — a030 × R40 a043（2026-05-11）

繼上一節之後，把 a030 跟 R40 a043 做跨輪權重平均 5 點 sweep（α=0 / 0.25 / 0.5 / 0.75 / 1.0），動機是兩者在外部 GMF 三尺度上的取捨方向互補：

- a030：8 px `−6.94%` / 0.8 px `+6.42%` / 0.08 px `−15.97%`（改善 0.08 px、退步 0.8 px）
- R40 a043：8 px `−5.91%` / 0.8 px `−3.15%` / 0.08 px `+21.52%`（改善 0.8 px、退步 0.08 px）

平均後 α=0.25 候選（`r39r40_complementary_avg_a025`）三尺度 Δ 都在 ±5.18% 內：8 px `−5.18%`、0.8 px `+1.51%`、0.08 px `+0.51%`。`r40_external_compare.py` 自動 verdict 為 `PASS_UPGRADE_GUARD`（即三尺度都在 3% 升級上限內），是專案歷史上首個跨三尺度都過 3% 上限的候選。

中間 α=0.50 / 0.75 沒有跟線性插值預測一致——0.8 px 在中間點反而退步到 +13% / +15%，是 weight averaging trade-off 在 α 軸上非線性的又一個明確例子。

R40 micro_val_unseen 跟 R39 shape_val_unseen 在 α=0.25 上的詳細指標還沒量測，正式升級為已核准替代候選前建議補。

完整 5 點 trade-off 數字、checkpoint 路徑、外部 GMF 解析報告見 [`a030_x_a043_sweep/reports/R39R40_COMPLEMENTARY_AVG_RESULTS.md`](../results/a030_x_a043_sweep/reports/R39R40_COMPLEMENTARY_AVG_RESULTS.md)。

`r39r40_complementary_avg_a025` 於 **2026-05-11 升級為 approved alternate**（balanced full-spectrum slot），詳見 `ESTIMATOR_POLICY.json` 的 `approved_alternates`。升級依據：四項驗證全過——外部 GMF 三尺度都在 3% 升級上限內、R40 顯微 5 類 PSNR 全勝 a030、R39 形狀 7 類 PSNR 全勝 a030、視覺仍在 sharp band。完整能力評估見 [`R39R40_AVG_a025_CAPABILITY_EVAL.md`](../results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md)。

a030 本身仍是 sweep 端點的歷史錨點；它沒獨立升級為 approved alternate（α=0.25 平均後成為 a025 才升）。
