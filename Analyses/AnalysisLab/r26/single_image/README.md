# R26 單張影像幾何分析

## 分析目標

用一張 demo 影像（input 原始模糊影像 + R26 重建 output）做靜態的幾何品質評估。回答的核心問題是：**R26 重建有沒有真的改善環形邊界的幾何精度，改善了多少，有沒有引入新的問題？**

這是序列分析的前置步驟。先在單張上確認改善是真實的，再用多幀驗證穩定性。

## 目錄結構

```
single_image/
├── scripts/
│   └── run_single_image_analysis.py    # 主分析腳本（~1800 行，包含所有分析函式和繪圖）
├── tests/
│   └── test_single_image_analysis.py   # 5 項 pytest
├── inputs/
│   ├── VisionTop_20251029182653732.bmp # Demo input 原始影像（1520x2180 px，8-bit BMP）
│   └── input_preview.png              # Input 的縮圖預覽
├── recon/
│   ├── output_preview.png             # R26 重建結果的縮圖預覽
│   └── reconstruct_progress_r26_sm035_best_tradeoff_in_Demo_Input_20260327_122202/
│       └── VisionTop_20251029182653732.bmp  # R26 重建結果（同檔名，同尺寸）
├── results/
│   ├── 01_edge_profiles.png           # Plot 01: 邊緣剖面
│   ├── 02_circle_fit.png              # Plot 02: 圓擬合
│   ├── 03_angular_consistency.png     # Plot 03: 角度一致性
│   ├── 04_frequency_spectrum.png      # Plot 04: 頻率頻譜
│   ├── 05_overview_and_artifacts.png  # Plot 05: 全圖概覽 + 偽影
│   ├── 06_edge_width_angular.png      # Plot 06: 邊緣寬度
│   ├── 07_residual_harmonics.png      # Plot 07: 諧波分解
│   ├── 08_residual_hotspot.png        # Plot 08: 殘差熱點
│   └── analysis_summary.json          # 所有量化指標的 JSON 摘要
└── reports/
    └── R26_SingleImage_Analysis_Report.md  # 完整中文分析報告（~75KB）
```

## Demo 影像資訊

| 項目 | 值 |
|------|------|
| 檔名 | VisionTop_20251029182653732.bmp |
| 影像尺寸 | 1520 x 2180 px |
| Annulus 圓心 | (771.7, 1508.0) px |
| 外半徑 | 597.0 px |
| 內半徑 | 485.5 px |
| 環寬 | 111.6 px |
| 偵測方法 | coarse_mask_seed + local_refine |

## 分析管線（7 步驟）

### Step 1: Annulus 偵測

從影像中自動偵測環形結構。先用粗粒度 mask（同心環亮度模板）定位大致區域，再用梯度下降做亞像素級精修。輸出圓心 (cx, cy)、內外半徑。

### Step 2: 360 角度邊緣提取

從圓心向外，每 1° 射出一條徑向射線（共 360 條）。沿每條射線取灰階梯度的最大值位置作為邊緣點。外邊界（亮→暗）和內邊界（暗→亮）分別提取。某些角度可能因為遮擋或噪聲沒有有效邊緣——這些會被標記為 invalid，不參與後續計算。有效角度約 324/360（coverage 90%）。

### Step 3: 圓擬合

對內外邊界各 ~324 個有效邊緣點做最小二乘法圓擬合（Kasa method）。得到：
- 擬合圓心 (fit_cx, fit_cy) 和半徑
- 殘差 = 每個邊緣點到擬合圓的距離（正值=外凸，負值=內凹）
- 殘差 std 和 max：衡量邊界偏離完美圓形的程度
- 圓心偏移：內外邊界的擬合圓心距離（若 annulus 是完美同心環，偏移應為 0）

### Step 4: 諧波分解（DFT）

對 360 點殘差序列做離散傅立葉變換，把殘差分解為不同角頻率的正弦分量：
- **k=1**（360° 周期）：整個邊界往某個方向偏移（圓心定位誤差）
- **k=2**（180° 周期）：橢圓形偏差（像散或 annulus 真實橢圓）
- **k=3**（120° 周期）：三葉形偏差
- **k>3**：局部缺陷（顆粒、划痕等）

### Step 5: 能量拆分 + Bootstrap CI

把諧波能量分為兩組：
- **低階幾何能量**（k=1,2,3）：可以用幾何模型解釋的偏差
- **高階缺陷能量**（k>3）：局部隨機缺陷

用 Bootstrap 2000 次重採樣計算兩組能量比例的 95% 信賴區間。這比只報「dominant k 是幾」更嚴謹——它告訴你「低階能量佔多少 ± 不確定度」。

### Step 6: 熱點聚集分析

以殘差絕對值的 75th percentile 為門檻，把超標的角度標記為「hot」。然後找出連續 hot 角度的 cluster（gap > 5° 就算不同 cluster）。量化指標：
- cluster 數量
- 總弧長（所有 cluster 的角度加總）
- 最大 cluster 寬度（最長的連續高殘差弧段）

### Step 7: 邊緣寬度量測

對每個角度方向，沿徑向的灰階剖面計算 10-90% rise distance（從暗到亮的上升距離）。這直接反映邊界的銳度——越小越銳利。

## 圖表說明

### Plot 01: 邊緣剖面 (`01_edge_profiles.png`)
8 個代表性角度方向（0°, 45°, 90°, ...）的徑向灰階剖面。每個角度畫 input 和 output 的對比。可以直觀看到 output 的邊緣梯度更陡峭。

### Plot 02: 圓擬合 (`02_circle_fit.png`)
把擬合圓疊在原始影像上。左半 = input + 擬合圓，右半 = output + 擬合圓。可以看到 output 的擬合圓和真實邊界更貼合。

### Plot 03: 角度一致性 (`03_angular_consistency.png`)
360° 的殘差分佈圖（角度 vs 殘差值）。可以看出殘差是均勻分佈（噪聲主導）還是有特定角度偏高（結構缺陷）。

### Plot 04: 頻率頻譜 (`04_frequency_spectrum.png`)
殘差的 DFT 功率頻譜。X 軸是角頻率 k，Y 軸是能量。可以看到 output 的低頻（k=1,2,3）是否有主導峰。

### Plot 05: 全圖概覽 + 偽影 (`05_overview_and_artifacts.png`)
全圖縮略 + 邊緣區域的 zoom-in。用來檢查反卷積有沒有引入 ringing、條紋等偽影。

### Plot 06: 邊緣寬度 (`06_edge_width_angular.png`)
360° 的邊緣寬度分佈圖。可以看出 output 是否在所有角度都更銳利，還是某些角度反而退步。

### Plot 07: 諧波分解 (`07_residual_harmonics.png`)
三欄佈局：左 = 殘差極座標圖，中 = DFT 頻譜長條圖，右 = 低階/高階能量拆分 + Bootstrap 95% CI 誤差棒。每行一個條件（input outer / input inner / output outer / output inner）。

### Plot 08: 殘差熱點 (`08_residual_hotspot.png`)
殘差的角度熱點圖 + cluster 統計標註。可以看出高殘差集中在哪些角度範圍，以及 output 是否成功消除了 input 的熱點。

## 關鍵結果

### 邊界精度改善

| 邊界 | Input 殘差 std | Output 殘差 std | 改善 |
|------|--------------|----------------|------|
| 外邊界 | 6.45 px | 2.63 px | **59.2%** |
| 內邊界 | 6.25 px | 2.95 px | **52.8%** |

### 邊緣銳度改善

| 邊界 | Input 寬度 | Output 寬度 | 改善 |
|------|-----------|------------|------|
| 外邊界 | 35.6 px | 22.6 px | **36%** |
| 內邊界 | 36.2 px | 22.8 px | **37%** |

### 諧波能量分佈

| 條件 | 低階能量 (k≤3) | 高階能量 (k>3) | 主導 k | 95% CI (低階) |
|------|-------------|-------------|--------|-------------|
| Input 外 | 1.4% | 98.6% | k=15 | [0.9%, 8.2%] |
| Input 內 | 1.1% | 98.9% | k=4 | [0.7%, 7.7%] |
| Output 外 | 11.1% | 88.9% | k=4 | [9.9%, 18.3%] |
| Output 內 | **23.1%** | 76.9% | **k=2** | **[15.1%, 33.3%]** |

Output 內邊界的低階能量 23.1%（CI 排除 0）由 k=2 橢圓模式主導——需要序列分析驗證這是固定偏置還是幀間波動。

### 熱點聚集

| 條件 | Cluster 數 | 總弧長 | 最大 cluster |
|------|-----------|--------|------------|
| Input 外 | 20 | 145° | 28° |
| Output 外 | 17 | 96° | **49°**（結構缺陷暴露） |
| Input 內 | 27 | 132° | 34° |
| Output 內 | 14 | 109° | 29° |

Output 外邊界的最大 cluster 反而變大（28°→49°），這是因為反卷積移除噪聲後，一個本來被噪聲掩蓋的結構缺陷被暴露了。

## 測試

5 項 pytest，驗證：
1. 合成環形影像的 annulus 偵測正確性
2. 圓擬合的殘差 std 在合理範圍
3. 分析 summary JSON 的結構完整性
4. 諧波分解的能量拆分欄位存在
5. 熱點 cluster 量化欄位存在

```bash
pytest Analyses/AnalysisLab/r26/single_image/tests/ -q
```

## 自含性

本分析是完全自含的：
- `inputs/VisionTop_20251029182653732.bmp`：原始 demo 影像（tracked）
- `recon/.../VisionTop_20251029182653732.bmp`：R26 重建結果（tracked）

任何人 clone 這個 repo 就能跑 `run_single_image_analysis.py`，不需要外部資料。
