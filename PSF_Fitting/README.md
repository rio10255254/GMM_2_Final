# PSF_Fitting — 說明文件 / Documentation

## 概覽

本資料夾實現「以 Zernike 多項式描述像差，並透過 BADS 最佳化演算法擬合 2D PSF」的完整工作流程，最終以擬合結果執行 Wiener 反捲積驗證。

**整體三階段流程：**

```
┌─────────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│  [階段 1] PSF 模擬   │     │   [階段 2] PSF 像差擬合   │     │ [階段 3] 反捲積驗證  │
│  SimulatePSF/       │ ──▶ │  HDR_fitting_2D*.m       │ ──▶│  Deconvolution/     │
│  psf_multi.mat      │     │  BADS 最佳化 Zernike 係數 │     │  Wiener 反捲積       │
└─────────────────────┘     └──────────────────────────┘     └─────────────────────┘
```

- **階段 1** 根據光學系統參數計算理論（無像差）PSF 作為初始基底
- **階段 2** 在此基底上加入 Zernike 像差擾動，令模擬影像與量測影像的 Loss 最小化
- **階段 3** 用擬合出的 PSF 對實驗影像執行 Wiener 反捲積，並與 SEM Ground Truth 比較

---

## 資料夾結構

```
PSF_Fitting/
│
├── README.md                           ← 本文件
├── HDR_fitting_2D.m                    ← 主程式 A：單張影像 PSF 擬合
├── HDR_fitting_2D_WholeFOV.m           ← 主程式 B：全 FOV 批次 PSF 擬合（推薦）
│
├── SimulatePSF/                        ← [階段 1] PSF 理論模擬
│   ├── psf_multiwavelength_2D.m        ← 執行此檔以重新產生 PSF（詳見階段 1）
│   ├── MicroscPSF.m                    ← Gibson-Lanni 顯微鏡 PSF 計算核心
│   ├── normlz.m                        ← Min-Max 正規化輔助函式（擬合程式需要）
│   ├── spectrum.mat                    ← 光源光譜加權資料（跨波長積分用）
│   └── psf_multi.mat                   ← ★ [輸出/輸入] 模擬產生的 2D PSF
│
├── Crop_circle_FreqFiltered/           ← [階段 2B 輸入] 全 FOV 批次影像
│   ├── VisionTop_YYYYMMDDHHMMSS_1.bmp
│   ├── VisionTop_YYYYMMDDHHMMSS_2.bmp
│   ├── ... (共 100 張，對應 10×10 FOV 格點)
│   ├── GT/
│   │   └── GT_901_with_Block_proc.bmp  ← Ground Truth（圓形柱 BMP）
│   └── Fits/                           ← ★ [階段 2B 輸出] 程式執行後自動建立
│       ├── batch_results.csv
│       └── PSF_fitted_2D_FOVstack.mat
│
├── SingleImage_Input/                  ← [階段 2A 輸入] 單張版影像
│   ├── VisionTop_20250903160550_freqDenoise.bmp  ← 頻率濾波後的量測影像
│   └── GT/
│       └── GT_901_with_Block_proc.bmp  ← Ground Truth（同上）
│
└── Deconvolution/                      ← [階段 3] 反捲積驗證
    ├── GT/
    │   └── pillar_30_SEM.tiff          ← SEM Ground Truth（用於驗證誤差）
    ├── TestImages/
    │   └── 30.tiff                     ← 待反捲積的實驗影像
    ├── PSF/
    │   └── PSF_fitted_2D.mat           ← 預先擬合好的 PSF（可直接跳至階段 3）
    └── Results/                        ← ★ [階段 3 輸出] 程式執行後自動建立
        └── deconv_result_2D.tiff
```

---

## 使用前準備

### 1. MATLAB Current Folder

**執行任何程式前，必須將 MATLAB Current Folder 設為本資料夾：**

```
d:\GMM_2_Final\PSF_Fitting\
```

所有程式中的路徑均為相對此目錄的相對路徑。

### 2. 加入 MATLAB Path

`normlz.m` 位於 `SimulatePSF/` 子資料夾，需加入 Path 才能被主程式呼叫：

```matlab
addpath(fullfile(pwd, 'SimulatePSF'));
```

建議在 MATLAB **Home → Set Path → Add Folder** 永久加入，避免每次重新執行。

### 3. 必要工具箱與套件

| 套件 | 用途 | 備註 |
|------|------|------|
| **BADS** (Acerbi & Ma, 2017) | PSF 擬合與 NSR 最佳化 | 需另行下載，非 MATLAB 內建 |
| Image Processing Toolbox | `imread`, `imresize`, `deconvwnr`, `imgradient` | MATLAB 內建 |
| Parallel Computing Toolbox | `gpuArray`, `gather` | 需 NVIDIA GPU；僅階段 2 使用 |

---

## 各階段詳細說明

---

### 階段 1：PSF 模擬（選用）

**程式：** `SimulatePSF/psf_multiwavelength_2D.m`

若需根據不同光學參數重新計算理論 PSF，執行此程式。光學系統參數如下：

| 參數 | 數值 | 說明 |
|------|------|------|
| `NA` | 0.23 | 物鏡數值孔徑 |
| `M` | 20× | 放大倍率 |
| `lambda` | 580 nm | 計算波長（目前僅單波長） |
| `resLateral` | 0.125 μm | 橫向像素尺寸 |
| `resAxial` | 74 nm | 軸向切片間距 |
| `pZ` | 0 | 焦平面偏移量（0 = 正焦） |
| PSF 大小 | 101×101 | 輸出陣列尺寸 |

> **注意：** 雖然腳本名稱含 "multiwavelength"，目前迴圈僅對 580 nm 計算一次，
> 光譜加權已預留但暫時為單波長模式。若要改為多波長積分，修改 `for j = 580:580`。

**輸出：** `SimulatePSF/psf_multi.mat`（變數 `psf_multi`，101×101 double，能量歸一化至總和=1）

> 若不需更新光學參數，跳過此步驟，直接使用現有的 `psf_multi.mat`。

---

### 階段 2A：單張影像 PSF 擬合

**程式：** `HDR_fitting_2D.m`（Section 1，執行到第一個 `%%` 為止）

**輸入：**

| 檔案 | 路徑 |
|------|------|
| 理論 PSF | `SimulatePSF/psf_multi.mat` |
| 量測影像 | `SingleImage_Input/VisionTop_20250903160550_freqDenoise.bmp` |
| Ground Truth | `SingleImage_Input/GT/GT_901_with_Block_proc.bmp` |

**執行方式：** 在 MATLAB 開啟後，點選 Section 1，按 `Ctrl+Enter` 執行（或直接 `Run`）。

**最佳化設定：**
- 最佳化變數：15 個（`x0` 向量）
- `x(1:14)` → 透過**非直觀的係數重映射**轉換為 14 個 Zernike 係數 C(1:14)
- `x(15)` → 振幅縮放 `AC`
- Tilt 項（Z1, Z2）並**未**在此版本中鎖死，整個 C 向量均為優化目標

**Loss 函數：**
```
Loss = 1 × MSE(頻率域) + 2×10⁵ × MSE(梯度域，normalized)
```

**輸出：** `SimulatePSF/PSF_fitted_2D_0924.mat`（含 `fitted_psf`, `x`, `fval`）

---

### 階段 2B：全 FOV 批次 PSF 擬合（推薦）

**程式：** `HDR_fitting_2D_WholeFOV.m`（Section 1）

**輸入：**

| 檔案 | 路徑 |
|------|------|
| 理論 PSF | `SimulatePSF/psf_multi.mat` |
| 批次影像（100 張） | `Crop_circle_FreqFiltered/VisionTop_*.bmp` |
| Ground Truth | `Crop_circle_FreqFiltered/GT/GT_901_with_Block_proc.bmp` |

**執行方式：** 在 MATLAB 直接 `Run`，程式自動依序處理全部 100 張影像。

**最佳化設定：**
- 最佳化變數：15 個（同上）
- `x(1:14)` → 直接映射為 Zernike Z2~Z15，其中 **Z2（Y-tilt）與 Z3（X-tilt）在函式內部強制為 0**（防止優化結果退化為純平移）
- `x(15)` → 振幅縮放 `AC`

**Loss 函數：**
```
Loss = 1 × MSE(頻率域) + 8×10⁴ × MSE(梯度域，normalized)
```

**Warm-start 機制：** 每一張影像的最佳化以**前一張的結果**作為初始點，加速收斂並提升連續 FOV 之間的一致性。第一張使用預設初始值 `x0 = [0 0 0 0 0 0 0 0 0 0 0 0 0 0 1.0]`。

**效能選項：**
```matlab
ENABLE_PLOTS = false;  % 關閉即時繪圖可大幅加速批次執行
```

**影像排序規則：** 依檔名末尾數字（`_1`, `_2`, …, `_100`）自然排序，對應 10×10 FOV 格點，row-major 左至右、上至下：

```
[ _1   _2  ...  _10 ]  ← row 1
[ _11  _12 ...  _20 ]  ← row 2
         ⋮
[ _91  _92 ... _100 ]  ← row 10
```

**輸出（自動建立於 `Crop_circle_FreqFiltered/Fits/`）：**

| 檔案 | 內容 |
|------|------|
| `batch_results.csv` | 每張影像的 fval、迭代次數、耗時（秒）|
| `PSF_fitted_2D_FOVstack.mat` | 全 FOV PSF 陣列，結構詳見下方 |

```matlab
fov_psf_data.psf_grid        % double [H, W, 10, 10]  — 各 FOV 點的 fitted PSF
fov_psf_data.coef_grid       % double [15, 10, 10]     — 對應的 Zernike 係數向量
fov_psf_data.fval_map        % double [10, 10]          — 擬合誤差
fov_psf_data.iterations_map  % double [10, 10]          — BADS 迭代次數
fov_psf_data.filename_map    % string [10, 10]          — 對應輸入檔名
```

**將全 FOV 擬合結果畫成附圖那種總覽圖：**

專案根目錄提供 `visualize_fitted_psf_grid.m`，可直接把 `PSF_fitted_2D_FOVstack.mat` 轉成一張 2D heatmap：

```matlab
visualize_fitted_psf_grid
```

若要調整每顆 PSF 的中心裁切範圍、縮圖大小與輸出檔，可用：

```matlab
visualize_fitted_psf_grid([], ...
    'CropSize', 17, ...
    'TileSize', 5, ...
    'GapSize', 1, ...
    'NormalizeEachPSF', true, ...
    'OutputPath', 'Crop_circle_FreqFiltered/Fits/fitted_psf_grid.png');
```

- `CropSize`：從每顆 fitted PSF 中心裁切的視窗大小
- `TileSize`：每顆 PSF 縮成幾乘幾像素後再拼圖
- `NormalizeEachPSF=true`：逐顆以自身峰值正規化，較容易觀察形狀差異
- `UseLogScale=true`：可進一步壓縮動態範圍，讓弱側瓣更明顯

---

### 兩版程式差異對照

| 項目 | HDR_fitting_2D.m（單張版） | HDR_fitting_2D_WholeFOV.m（批次版） |
|------|--------------------------|-------------------------------------|
| 處理影像數 | 1 張（寫死路徑） | 100 張（自動掃描資料夾） |
| Zernike 映射 | 非直觀重映射（C 向量重排） | 直接映射 Z2~Z15 |
| Tilt 鎖定 | 否（Z1, Z2 為優化目標） | 是（Z2=0, Z3=0 強制鎖死） |
| Warm-start | 否（每次從 x0 開始） | 是（以前一張結果作初始點） |
| PSF Precompute | 否 | 是（FFT、pupil grid 只算一次） |
| Loss 梯度權重 | 2×10⁵ | 8×10⁴ |
| 輸出格式 | 單一 `.mat` | FOV stack `.mat` + summary `.csv` |

---

### 階段 3：Wiener 反捲積驗證

位於 `HDR_fitting_2D.m` 或 `HDR_fitting_2D_WholeFOV.m` 的 **Section 2**（第二個 `%%` 之後）。可獨立執行，不依賴 Section 1 的結果（直接讀取 `Deconvolution/PSF/PSF_fitted_2D.mat`）。

**輸入：**

| 檔案 | 路徑 |
|------|------|
| 擬合好的 PSF | `Deconvolution/PSF/PSF_fitted_2D.mat` |
| 實驗影像 | `Deconvolution/TestImages/30.tiff` |
| SEM Ground Truth | `Deconvolution/GT/pillar_30_SEM.tiff` |

**執行方式：** 選取 Section 2，按 `Ctrl+Enter`。

**最佳化邏輯：** BADS 搜尋最佳 NSR（Noise-to-Signal Ratio）參數，範圍 `[1e-3, 1e3]`，Loss 為：

```
Loss = 100 × MSE( imgradient(反捲積結果), imgradient(SEM GT) )
```

**輸出：** `Deconvolution/Results/deconv_result_2D.tiff`（16-bit TIFF）

---

## 各函式說明

| 函式 | 位置 | 說明 |
|------|------|------|
| `aberration(coef)` | `HDR_fitting_2D*.m` 內 | 計算 Zernike 像差 PSF 並回傳 Loss，供 BADS 呼叫 |
| `wnrbads(input)` | `HDR_fitting_2D*.m` 內 | 計算 Wiener 反捲積梯度誤差，供 BADS 呼叫 |
| `normlz(x)` | `SimulatePSF/normlz.m` | Min-Max 正規化至 [0,1]，支援 gpuArray<br>實作：`(x - min(x)) / (max(x) - min(x) + eps)` |
| `MicroscPSF(param)` | `SimulatePSF/MicroscPSF.m` | Gibson-Lanni 模型計算理論 PSF，回傳 max-normalized 陣列 |

---

## 常見問題

**Q: 執行時出現 `Undefined function 'normlz'`**
A: 尚未加入 Path。在 MATLAB 執行：
```matlab
addpath(fullfile(pwd, 'SimulatePSF'));
```

**Q: 執行時出現 `No input images found in Crop_circle_FreqFiltered`**
A: MATLAB Current Folder 未設為 `PSF_Fitting/`。確認後重新執行。

**Q: `Expected 100 images for a 10x10 grid, but found N files`**
A: `grid_rows × grid_cols` 必須等於資料夾內的圖片數量。修改程式頂端的 `grid_rows` 與 `grid_cols`。

**Q: GPU 相關錯誤（`gpuArray` 失敗）**
A: 確認電腦配備支援 CUDA 的 NVIDIA GPU，且已安裝 Parallel Computing Toolbox。
階段 3 的反捲積全程在 CPU 執行，不受影響。

**Q: `bads` 函式找不到**
A: BADS 工具箱未安裝或未加入 Path。至 [BADS GitHub](https://github.com/acerbilab/bads) 下載後加入 MATLAB Path。

---

## 版本紀錄

| 日期 | 內容 |
|------|------|
| 2025-09-24 | 單張版 (`HDR_fitting_2D.m`) 完成 2D 化 |
| 2025-10 | WholeFOV 批次版加入 Warm-start、Precompute 優化、Tilt 鎖定 |
| 2026-03-04 | 路徑全面改為相對路徑，整合至 `d:\GMM_2_Final\PSF_Fitting\`；新增本說明文件 |

---

## English Companion Guide

### Overview

This folder implements a full workflow for describing aberrations with Zernike
polynomials, fitting a 2D PSF with BADS optimization, and validating the fitted
PSF through Wiener deconvolution.

The overall workflow has three stages:

1. **PSF simulation**
   - generate a theoretical PSF as the optical baseline
2. **PSF aberration fitting**
   - fit Zernike coefficients so the simulated image matches measured data
3. **Deconvolution validation**
   - use the fitted PSF in Wiener deconvolution and compare against SEM ground
     truth

### Folder Structure

Important top-level files:

- `HDR_fitting_2D.m`
  - single-image PSF fitting
- `HDR_fitting_2D_WholeFOV.m`
  - full-FOV batch PSF fitting (recommended main path)
- `README.md`
  - this document

Important subfolders:

- `SimulatePSF/`
  - theoretical PSF simulation inputs and outputs
- `Crop_circle_FreqFiltered/`
  - full-FOV batch input images and fitting outputs
- `SingleImage_Input/`
  - single-image fitting input set
- `Deconvolution/`
  - Wiener deconvolution validation assets and outputs

### Before You Start

Make sure:

1. MATLAB current folder is set to:
   `d:\GMM_2_Final\PSF_Fitting\`
2. `SimulatePSF/` is added to the MATLAB path so `normlz.m` can be resolved
3. required toolboxes / packages are available:
   - BADS
   - Image Processing Toolbox
   - Parallel Computing Toolbox (for GPU-enabled fitting)

### Stage 1: PSF Simulation

Main script:

- `SimulatePSF/psf_multiwavelength_2D.m`

Use it when you need to regenerate the theoretical PSF from optical system
parameters such as NA, magnification, wavelength, and sampling resolution.

The main output is:

- `SimulatePSF/psf_multi.mat`

If the optical setup has not changed, you can usually reuse the existing
`psf_multi.mat`.

### Stage 2A: Single-Image PSF Fitting

Main script:

- `HDR_fitting_2D.m`

Inputs:

- theoretical PSF from `SimulatePSF/psf_multi.mat`
- measured image from `SingleImage_Input/`
- GT image from `SingleImage_Input/GT/`

This path fits one image at a time and writes a fitted PSF `.mat` file such as
`PSF_fitted_2D_0924.mat`.

### Stage 2B: Whole-FOV Batch Fitting

Main script:

- `HDR_fitting_2D_WholeFOV.m`

Inputs:

- theoretical PSF
- 100 full-FOV BMP images in `Crop_circle_FreqFiltered/`
- GT image in `Crop_circle_FreqFiltered/GT/`

This is the recommended path because it:

- processes the full 10x10 FOV grid
- supports warm-starting from the previous image
- precomputes shared pieces for speed
- stores the final result as a structured FOV PSF stack

Main outputs:

- `Crop_circle_FreqFiltered/Fits/batch_results.csv`
- `Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`

### Visualizing the Fitted FOV Grid

The repository root provides:

- `visualize_fitted_psf_grid.m`

Use it to render the fitted FOV stack as a compact 2D visualization. This is
useful for quickly seeing whether the PSF shape varies smoothly or irregularly
across the full field of view.

### Stage 3: Wiener Deconvolution Validation

This stage lives in Section 2 of the fitting scripts and can be run separately.

Inputs:

- fitted PSF
- test image
- SEM ground truth

The validation searches for a good Wiener NSR setting and writes the final
deconvolved image to:

- `Deconvolution/Results/deconv_result_2D.tiff`

### Single-Image vs Whole-FOV Difference

The two fitting scripts differ in important ways:

- the single-image version fits one image only
- the WholeFOV version fits 100 images in a 10x10 grid
- the WholeFOV version uses warm-starting and precompute
- the mapping / handling of tilt terms differs
- the weighting of gradient-related fitting terms also differs

If you are working with the repository as it is used today, the batch
WholeFOV path is the more important operational workflow.

### Common Issues

Typical setup problems include:

- MATLAB cannot find `normlz`
- current folder is not `PSF_Fitting/`
- the expected 10x10 image count is wrong
- GPU / `gpuArray` support is unavailable
- BADS is not installed or not on the MATLAB path

These are usually environment or path issues rather than fitting-logic issues.

### Version Notes

- `2025-09-24`
  - single-image 2D fitting version completed
- `2025-10`
  - WholeFOV batch fitting added warm-start, precompute, and tilt locking
- `2026-03-04`
  - paths were normalized to relative-path usage under
    `d:\GMM_2_Final\PSF_Fitting\` and this documentation was added
