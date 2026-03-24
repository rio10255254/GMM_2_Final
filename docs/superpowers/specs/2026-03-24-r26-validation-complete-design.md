# R26 統一驗證包設計規格

**日期**：2026-03-24
**專案**：GeoEdge R26 交付包
**目的**：將現有分散的驗證分析整合為單一學術級驗證包，並新增環形結構專項分析

---

## 背景與動機

現有驗證材料分散於兩個獨立 bundle（共 50+ 個檔案），部分圖表重複，缺乏針對環形結構的專項分析，且無統一的主報告將所有維度串接。目標是：
1. 去蕪存菁，精選 10 張有效圖表
2. 新增 4 個環形結構專項分析模組
3. 整合成一個可直接支持報告/論文引用的驗證包

---

## 輸出結構

```
D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包\輸出結果\驗證分析\
├── R26_OBJECTIVE_VALIDATION_ANALYSIS_20260324.md   （已有，保留）
└── R26_validation_complete\                         （新建）
    ├── R26_完整驗證總報告.md                        （主報告）
    ├── figures\                                     （精選 10 張學術圖表）
    │   ├── 01_batch_contact_sheet.png               （現有，複製精選）
    │   ├── 02_radial_profile_crosscase.png          （★新）
    │   ├── 03_edge_sharpness_slope.png              （★新）
    │   ├── 04_ring_roi_metrics.png                  （★新）
    │   ├── 05_batch_metric_heatmap.png              （★新）
    │   ├── 06_histogram_comparison.png              （精選自 single bundle）
    │   ├── 07_frequency_spectrum.png                （精選自 single bundle）
    │   ├── 08_ssim_map.png                          （精選自 single bundle）
    │   ├── 09_mtf_comparison.png                    （精選自 single bundle）
    │   └── 10_difference_spatial_analysis.png       （精選自 single bundle）
    └── data\
        ├── batch_metrics.csv                        （複製自 batch bundle）
        ├── batch_summary.json                       （複製自 batch bundle）
        ├── basic_metrics.json                       （複製自 single bundle）
        ├── ring_analysis_summary.json               （★新，環形分析匯總）
        └── input_integrity_check.json               （複製自 single bundle）
```

---

## 四個新分析模組

### 前置步驟：環形幾何偵測（所有模組共用）

`batch_metrics.csv` 與 `batch_summary.json` 僅含 DELTA 值，無各圖的環形絕對座標。
Module 2 和 Module 3 均需絕對環中心座標 (cx, cy) 與峰值半徑。

**方法**：對 10 張 input BMP 各執行 Hough Circle 偵測（與單圖分析相同流程）：
- 灰階轉換 → GaussianBlur → HoughCircles（params 參考 basic_metrics.json：radius≈539px）
- 輸出：`ring_geometry_per_image.json`（含各圖 cx, cy, peak_radius, fwhm）
- 若偵測失敗，fallback 使用 case 01 的幾何值（773, 1512, 539）

---

### Module 1：邊緣銳利度（Edge Slope + FWHM）

**目的**：量化 R26 是否讓環邊緣過渡更銳利

**重要背景**：case 01 的 FWHM 在 input/output 間不變（均為 109px），但邊緣最大斜率有大幅提升（rising slope: 2.05→5.25, +157%；falling slope: 2.09→5.96, +186%）。因此主指標改為**邊緣最大斜率**，FWHM 作為輔助指標。

**方法**：
- 對 10 張圖，各於環邊緣附近取徑向強度剖面
- 計算 ESF 並微分得 LSF
- 量測：(1) LSF 峰值（max slope）；(2) LSF 的 FWHM
- 分別對 input 與 output 計算

**輸出圖表** `03_edge_sharpness_slope.png`：
- 上下兩子圖：上為最大斜率（主指標），下為 FWHM（輔助）
- 各子圖：雙柱條形圖，橫軸 10 案例，input（淺色）vs output（深色）
- 含整體均值標註橫線
- 學術配色（灰/黑），清晰標籤

**寫入 JSON**：每張圖的 `input_max_slope`、`output_max_slope`、`slope_improvement_pct`、`input_fwhm`、`output_fwhm`

---

### Module 2：跨案例徑向輪廓一致性

**目的**：展示 R26 讓環形輪廓跨影像更一致（低變異）

**方法**：
- 從前置步驟產生的 `ring_geometry_per_image.json` 讀取各圖環中心 (cx, cy) 與峰值半徑
- 各圖提取以環中心為基準的徑向強度輪廓，以環峰值位置對齊
- 計算 10 條 input 輪廓的 mean ± std 及 10 條 output 輪廓的 mean ± std
- 量測 std 曲線下面積（AUC-std）作為一致性指標

**輸出圖表** `02_radial_profile_crosscase.png`：
- 左右並排兩子圖：左為 input 組、右為 output 組
- 各疊 10 條細線（半透明）+ 粗均值線 + std 陰影帶
- 統一 Y 軸範圍，方便直接比較
- 學術折線圖風格

**寫入 JSON**：`input_std_auc`、`output_std_auc`、`consistency_improvement_pct`

---

### Module 3：環 ROI 局部指標

**目的**：在環形區域（而非全圖）計算品質指標，使數字更能代表 GMF 量測區域

**方法**：
- 從 `ring_geometry_per_image.json` 讀取各圖環中心與峰值半徑
- 定義環形 ROI 遮罩：內徑 = radius − fwhm/2，外徑 = radius + fwhm/2（以 FWHM 決定帶寬，case 01 fwhm=109px 故帶寬±54px）
- 在 ROI 區域內計算三個指標：
  1. **ROI SNR**：環峰值強度 / ROI 內背景標準差（MAD 估計）
  2. **ROI Weber Contrast**：(環峰值 − 鄰近背景均值) / 鄰近背景均值
  3. **ROI Gradient P95**：ROI 內 Sobel 梯度的 95th percentile

**輸出圖表** `04_ring_roi_metrics.png`：
- 三行子圖，每行一個指標
- 各行：10 案例橫軸，input vs output 配對連線圖（paired line plot）
- 配對連線可直觀看出每個案例的改善方向

**寫入 JSON**：各圖三指標的 input/output 值及差值

---

### Module 4：批次指標熱圖

**目的**：一圖呈現 10 張案例 × 多指標的改善幅度全覽

**方法**：
- 橫軸：10 個案例（VisionTop_...）
- 縱軸：6 個關鍵指標（環峰值對比增益、邊緣最大斜率改善率、ROI SNR 改善、ROI Weber Contrast 改善、梯度 P95 比值、熵變化）
- 每格數值為 output 相對 input 的改善量或比值
- 顏色編碼：RdBu_r 配色（藍=改善，紅=退步），數值標示在格內

**輸出圖表** `05_batch_metric_heatmap.png`：
- 學術 heatmap 風格，colorbar 含標籤
- 格內數字保留 3 位有效數字

---

## 主報告章節架構

`R26_完整驗證總報告.md`：

```
# R26 外部驗證完整總報告

## 1. 引言
   - 驗證目的、範圍、重要前提（無 GT）

## 2. 實驗設定
   - 模型、權重、影像來源、輸入完整性驗證

## 3. GMF 外部量化比較（最高權重）
   - 0.8px 主戰場：R18→R26 −32.98%
   - 8px 宏觀守衛：R18→R26 −19.82%
   - 0.08px 輕微回退注意事項

## 4. 環形結構專項分析
   4.1 邊緣銳利度（FWHM）       → 圖 03
   4.2 跨案例徑向輪廓一致性     → 圖 02
   4.3 環 ROI 局部指標          → 圖 04

## 5. 批次影像品質分析（n=10）
   - 批次彙總表
   - 批次指標熱圖               → 圖 05
   - 10 案例接觸表              → 圖 01

## 6. 單張代表案例深度分析（case 01）
   - 灰階分布                   → 圖 06
   - 頻域分析                   → 圖 07
   - SSIM 空間分布              → 圖 08
   - MTF 曲線                   → 圖 09
   - 差異影像                   → 圖 10

## 7. 各目標達成狀況總表

## 8. 限制與缺口
```

---

## 圖表規範

- 風格：學術（無裝飾性色彩，黑白或最小配色）
- 字型大小：軸標籤 ≥ 10pt，標題 ≥ 12pt
- 圖片解析度：≥ 150 DPI
- 配色：灰/黑為主，需要區分時使用 viridis 或 RdBu
- 無 3D 圖、無雷達圖、無過度裝飾

---

## 資料來源

| 資料 | 路徑 |
|------|------|
| 10 張輸入 BMP | `輸出結果\驗證分析\R26_external_batch_bundle\input_subset\` |
| 10 張輸出 BMP | `輸出結果\推論結果\reconstruct_progress_r26_sm035_best_tradeoff_in_input_subset_20260317_162050\` |
| 環形幾何（中心/半徑） | `輸出結果\驗證分析\R26_external_batch_bundle\batch_summary.json` |
| 現有單圖圖表 | `輸出結果\驗證分析\R26_external_single_bundle\` |
| 現有批次圖表 | `輸出結果\驗證分析\R26_external_batch_bundle\` |
| GMF 外部比較 | `docs\evidence\historical_baselines\EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.md` |

---

## 驗收標準

1. `R26_validation_complete\` 內所有圖表可獨立理解（含軸標籤、圖說）
2. 主報告每張圖有對應的數字依據（可追溯至來源文件或 JSON）
3. 四個新模組均有對應的 JSON 數值記錄（不只有圖）
4. 熱圖格內數值與 CSV/JSON 數據一致
5. 限制章節如實說明驗證集分離、無 GT 等缺口
