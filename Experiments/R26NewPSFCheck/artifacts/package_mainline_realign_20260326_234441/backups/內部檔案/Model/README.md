# 模型說明文件

## 概覽

本資料夾實現「以 PSF 物理先驗引導的邊界保真超解析（SR）/ 反捲積深度學習模型」。

模型名稱：**GeoEdgeAlignSR_v1_v5_NoCoord**

核心設計目標：
- **邊界幾何保真**：輸出影像的邊緣位置、寬度不因模型而產生偏移或模糊
- **PSF 物理先驗**：在 U-Net 前加入 Wiener 反捲積物理層，將光學像差系統性還原
- **Translation-Equivariance**：採用 anti-aliasing 上採樣，抑制 checkerboard 等週期性偽影

---

## 檔案結構

```
Model/
│
├── README.md                                              ← 本文件
│
├── GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py                ← 模型定義
├── GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py  ← 訓練腳本
├── GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py  ← 推論腳本
├── GeoEdgeAlignSR_v1_Utils.py                             ← 工具函式
```

`Test_Image/` 為可選監控資料夾，不是這份 handoff package 的必要內容。若不存在，訓練腳本會自動退回使用 `../Training_Data/tra_src_ring/` 的第一張影像作為 monitor。

**與本資料夾並列的相關路徑（程式以相對路徑存取）：**

```
GeoEdge_R26_Handoff/
├── Model/                        ← 本資料夾
├── Training_Data/                ← 訓練資料（src / label）
│   ├── tra_src_ring/             ← 輸入影像（量測圖）
│   └── tra_lbl_ring/             ← 目標影像（Ground Truth）
├── PSF_Fitting/                  ← PSF 擬合結果（供模型讀取）
│   └── Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat
├── Traing_Progress/              ← 訓練結果（checkpoint、log、圖表）
│   └── training_progress_{MODEL}_{timestamp}/
│       └── weights/
│           ├── best_tradeoff.pth.tar
│           ├── best_detail_guarded.pth.tar
│           └── latest.pth.tar
└── Reconstruct_Progress/         ← 推論結果
    └── reconstruct_progress_{timestamp}/
```

> **注意：** `Traing_Progress/` 資料夾名稱有拼寫錯誤（少一個 i），為歷史遺留，勿更名以免程式找不到路徑。

---

## 模型架構

### 整體結構

```
輸入圖 [B,1,H,W]
    │
    ▼
[物理層] PSFDeconvPhysics         ← 可選，Wiener 頻域反捲積（保守 α 殘差混合）
    │
    ▼
[Encoder]
  E1: ConvBlock + ResBlock  →  [B, 48,   H,   W]   ─────────────────────┐ skip f1
  ↓ stride-2 Conv                                                         │
  E2: ConvBlock + ResBlock  →  [B, 96,   H/2, W/2] ─────────────┐ skip f2│
  ↓ stride-2 Conv                                                 │        │
  E3: ConvBlock + ResBlock  →  [B, 192,  H/4, W/4] ───┐ skip f3 │        │
  ↓ stride-2 Conv                                      │          │        │
[Bottleneck]                                           │          │        │
  2×ResBlock               →  [B, 192,  H/8, W/8]    │          │        │
[Decoder]                                              │          │        │
  U3: ShiftSafeUpsample + cat(f3)                  ←──┘          │        │
  U2: ShiftSafeUpsample + cat(f2) → [WeakPSFDeconvBlock] ←──────┘        │
  U1: ShiftSafeUpsample + cat(f1)                              ←──────────┘
    │
    ▼
  1×1 Conv → [OpticalBandpassFilter(僅訓練時)] → Sigmoid
    │
    ▼
輸出圖 [B,1,H,W]  ∈ [0,1]
```

### 關鍵組件

#### 1. PSFDeconvPhysics（強物理層）

位於 U-Net 之前，對整張輸入圖做 Wiener 反捲積：

```
out = x + α × (Wiener(x, PSF) - x)
```

- `α`：可訓練，範圍 `[0.05, 0.35]`，初始值 0.10（保守殘差，不強行替換輸入）
- PSF 來源：FOV stack 的平均（`use_stack_mean=True`）或中心 PSF
- `reg`（正則化）：控制 Wiener 濾波的雜訊抑制強度，預設 10.0

#### 2. WeakPSFDeconvBlock（弱物理注入塊）

注入在 Decoder 的 y2 層（H/2 解析度），對特徵圖做局部去模糊引導：

- 從 FOV stack 選 **K=4** 個代表 PSF（中心 + 4 角）
- 以小型 Gating 網路（GAP → Conv → SiLU → Conv → Softmax）動態混合 K 個反捲積結果
- 僅對低頻部分作用（`lowfreq_ratio=0.25`），避免引入 HF 偽影
- 最終保守殘差混合：`out = x + β × (Σ w_k × Deconv_k(x) - x)`，`β ∈ [0, 0.10]`

#### 3. ShiftSafeUpsample（平移等變上採樣）

```
Bilinear × 2 → ReflectionPad2d(1) → DepthwiseConv(固定 Gaussian blur，不訓練) → Conv
```

以固定 Gaussian blur 抑制 aliasing，防止 checkerboard 偽影和 sub-pixel 平移敏感性。

#### 4. OpticalBandpassFilter（光學帶通濾波器）

**僅在訓練期間**作用，模擬顯微鏡 MTF cutoff（Butterworth 形狀），抑制模型輸出的超物理頻率成分：

```
H(ρ) = 1 / (1 + (ρ / cutoff)^(2×order))
```

推論時自動 bypass（`model.eval()` 後不執行）。

---

## 使用說明

### 環境依賴

```bash
pip install torch torchvision torchmetrics opencv-python scipy matplotlib tqdm numpy
```

Python 3.12，需 NVIDIA GPU（CUDA）進行訓練。

---

### 訓練

**執行前確認：**
1. `Training_Data/tra_src_ring/` 與 `Training_Data/tra_lbl_ring/` 已備妥（同檔名，src/lbl 一一對應）
2. `PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat` 存在（PSF 擬合輸出）

**執行方式（從 Model/ 資料夾）：**

```bash
cd Model
python GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py
```

**重要 `TrainConfig` 參數（程式頂端修改）：**

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `DEVICE` | `"cuda:0"` | 訓練裝置 |
| `LR` | `2e-5` | 初始學習率 |
| `BATCH_SIZE` | `4` | Batch size |
| `CROP_SIZE` | `256` | 訓練 patch 大小 |
| `NUM_EPOCH` | `100` | 總訓練 epoch 數 |
| `PSF_FITTED_PATH` | `../PSF_Fitting/.../PSF_fitted_2D_FOVstack.mat` | PSF 路徑 |
| `WEAK_PSF_K` | `4` | Weak PSF block 使用的代表 PSF 數量 |
| `SIMPLETEST_MODE` | `True` | 使用 SimpleTest 模式（精簡驗證） |

**訓練結果（自動建立於 `../Traing_Progress/`）：**

```
Traing_Progress/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_{timestamp}/
├── weights/
│   ├── best_tradeoff.pth.tar         ← 最佳整體 tradeoff checkpoint
│   ├── best_detail_guarded.pth.tar   ← 細節保護最佳 checkpoint
│   ├── GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_ema_best_tradeoff.pth.tar  ← EMA 版本
│   └── latest.pth.tar                ← 最後一個 epoch
├── logs/                              ← CSV 訓練 log
└── plots/                             ← Loss 曲線、GMF 指標圖
```

**訓練排程（50-epoch 節奏）：**

| Epoch | 主要事件 |
|-------|---------|
| E1–10 | Weak PSF 凍結；EQ（平移等變）loss 關閉 |
| E11–35 | Weak PSF beta 緩步增至 0.12；EQ ramp on |
| E36–80 | Weak PSF beta ramp 至 0.28 |
| E81–100 | Weak PSF beta 維持；EQ 緩降至 0.4 |

**Loss 組成（預設權重）：**

| Loss 項目 | 權重 | 說明 |
|----------|------|------|
| `W_REC` | 1.0 | 像素重建（L1 / MSE） |
| `W_GRADMAG` | 0.8 | 梯度幅值一致性（Sobel） |
| `W_EDGE_ORI_SIMPLE` | 0.3 | 邊緣方向一致性 |
| `W_EQ_GEOM` | 0.5 | 平移等變幾何一致性 |
| `W_STAT` | 0.10 | 統計（均值/方差）一致性 |
| `W_BAND` | 0.10 | 頻帶一致性 |
| `W_HF_LAP` | 0.15 | 高頻 Laplacian 細節恢復 |

---

### 推論

**執行方式（從 Model/ 資料夾）：**

```bash
cd Model
python GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py \
    --weights ../weights/r26_sm035_best_tradeoff.pth.tar
```

**自動行為：**
- 預設輸入：`../Training_Data/tra_src_ring/`
- 輸出至：`../Reconstruct_Progress/reconstruct_progress_{timestamp}/`
- 若 `../Traing_Progress/` 下沒有完整 training run，會 fallback 到 `../weights/r26_sm035_best_tradeoff.pth.tar`
- 不再使用任何 hidden select-mode 或個人資料夾 override

**常用 CLI 參數：**

```bash
python GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py \
    --weights ../weights/r26_sm035_best_tradeoff.pth.tar \
    --input-dir path/to/images/ \
    --device cuda:0 \
    --select-mode all          # all / odd / even
```

**PSF 相關參數（推論時）：**

```bash
# 從 checkpoint 中直接還原 PSF buffers（預設）
--psf-from-ckpt

# 或明確指定 PSF 路徑
--psf-fitted-path path/to/PSF_fitted_2D_FOVstack.mat
```

**推論結果結構：**

```
Reconstruct_Progress/reconstruct_progress_{timestamp}/
├── input/     ← 輸入影像的副本
├── output/    ← 模型推論結果（BMP/PNG）
└── diff/      ← 與 GT 的差異圖（若有提供 --gt-dir）
```

---

## 各程式說明

### `GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py`

模型定義，包含以下類別：

| 類別 | 功能 |
|------|------|
| `GeoEdgeAlignSR_v1_v5_NoCoord` | 主模型（U-Net + 物理層） |
| `PSFDeconvPhysics` | Wiener 頻域反捲積物理前處理層 |
| `WeakPSFDeconvBlock` | 多 PSF 軟混合反捲積注入塊 |
| `ConvBlock` | Conv + GroupNorm + SiLU |
| `ResBlock` | 2 層 ConvBlock 殘差塊 |
| `ShiftSafeUpsample` | Anti-aliasing 上採樣（×2） |
| `OpticalBandpassFilter` | 光學截止頻率模擬（訓練期間使用） |

`DepthwiseDeblurPhysics` 為 `PSFDeconvPhysics` 的別名，保留向後相容。

### `GeoEdgeAlignSR_v1_Utils.py`

| 函式 | 輸入 / 輸出 | 功能 |
|------|------------|------|
| `read_gray_u8(path)` | `str → np.uint8[H,W]` | 讀取灰階圖，自動轉 8-bit |
| `write_gray_u8(path, img)` | — | 儲存灰階圖，自動建立目錄 |
| `pad_to_multiple(x, m)` | `[B,C,H,W] → same, (pad_h, pad_w)` | 將 H,W 補至 m 的倍數（推論前常用） |
| `unpad(x, pad_h, pad_w)` | `[B,C,H,W] → same` | 裁切掉 pad_to_multiple 加的邊距 |
| `shift_tensor_subpixel(x, dx, dy)` | `[B,C,H,W] → same` | 次像素平移（grid_sample，支援 border/zeros/reflection 填充模式） |
| `sobel_magnitude(x)` | `[B,1,H,W] → [B,1,H,W]` | Sobel 梯度幅值 |
| `apply_hann_and_mask(x, mask)` | `[B,1,H,W] → same` | Mask + 去均值 + std 正規化 + Hann 窗（相位計算前置處理） |

---

## 訓練資料格式

| 資料集 | 路徑 | 說明 |
|--------|------|------|
| 訓練來源 | `../Training_Data/tra_src_ring/` | 量測影像（BMP/PNG），圓形 ring 裁切 |
| 訓練目標 | `../Training_Data/tra_lbl_ring/` | Ground Truth 影像，與 src 同檔名 |

- 影像為灰階（1 channel），訓練時隨機裁切 256×256 patch
- 訓練中自動合成子像素平移對（80% tiny <0.3px、18% mid 0.3–1px、2% integer 1–2px）

---

## 常見問題

**Q: 訓練時找不到 PSF 檔**
A: 確認 `PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat` 存在（需先執行 `PSF_Fitting/HDR_fitting_2D_WholeFOV.m` 的 Section 1）。

**Q: 推論時找不到 checkpoint**
A: `../Traing_Progress/` 下沒有完整的 training run。可透過 `--weights` 明確指定路徑：
```bash
python GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py \
    --weights ../weights/r26_sm035_best_tradeoff.pth.tar
```

**Q: PSF shape mismatch 錯誤**
A: 推論時預設 `--psf-from-ckpt`，會從 checkpoint buffer 重建 PSF，不需要外部 `.mat` 檔。若仍出錯，嘗試加上 `--no-psf-from-ckpt --psf-fitted-path path/to/PSF.mat`。

**Q: 模型輸出有明顯 checkerboard 偽影**
A: 確認使用 `ShiftSafeUpsample`（預設 `use_upsample_conv=True`）而非舊版 `UpsampleConv`。

---

## 版本紀錄

| 版本 | 日期 | 內容 |
|------|------|------|
| v5 | 2025-10 | Weak PSF block 加入；ShiftSafeUpsample；EQ loss 節奏化排程 |
| v5_NoCoord | 2025-10 | 移除 CoordConv（發現對邊界對齊無益） |
| return_v2_SimpleTest | 2025-11 | Zeros padding + mask erosion 修正邊界偽影；GMF 指標監控 |
| 2026-03-17 | — | 封裝為 `GeoEdge_R26_Handoff/`，移除 hidden override，補齊外部 handoff 文件與證據路徑 |


