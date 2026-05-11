# PSF 一條龍教學包 — 繁體中文版

這份資料夾把 `PSF_Fitting/` 模組的「正式版完整工作流」濃縮成一個可獨立執行、可打包分享的教學包,從零開始、從頭到尾示範:

1. **理論 PSF 建立** — 用 Gibson-Lanni 顯微鏡 PSF 模型 + 光源光譜加權,從光學系統參數算出無像差理論 PSF。
2. **PSF 像差擬合** — 在理論 PSF 上加 14 維 Zernike 多項式像差項 + 1 維振幅,用 BADS 全域最佳化把模擬影像逼近真實量測影像。
3. **Wiener 反捲積驗證** — 拿擬合好的 PSF 對實驗影像做反捲積,並與 SEM Ground Truth 比較。

整份教學包的程式碼、範例資料、BADS toolbox 全部自帶,接收者解壓後在 MATLAB 中只要兩個指令就能完整跑完。

---

## 0. 你會學到什麼

讀完並跑完這份教學包,你會了解:

- Gibson-Lanni PSF 模型的物理意義與主要參數 (NA / 波長 / 折射率 / 工作距離) 怎麼影響 PSF 形狀。
- 為什麼要把 PSF 表示成「無像差基底 × Zernike 像差相位」 — 而不是直接用 Gaussian 擬合。
- 為什麼用 BADS (Bayesian Adaptive Direct Search) 而不是 L-BFGS / fminunc — 全域 vs 區域最佳化的差別。
- Whole-FOV 批次擬合的資料結構 (10×10 grid 的 4D PSF stack)。
- 從 stack 抽單張 PSF 做 Wiener 反捲積,並用 NSR 參數最小化反捲積結果與 SEM GT 的梯度差異。

不會教什麼:本教學包不教 MATLAB 基礎語法、影像處理基礎,也不深入推導 Gibson-Lanni 的 Bessel 級數展開或 Zernike 多項式正交性。需要這些細節請查文末的引用文獻。

---

## 1. 環境需求

| 項目 | 必要性 | 說明 |
|---|---|---|
| MATLAB R2020b 以上 | 必要 | 程式用了 `string` 類別、`inputParser` parameter、`fullfile` 等現代用法 |
| Image Processing Toolbox | 必要 | `imread`, `imresize`, `imgradient`, `deconvwnr`, `Tiff` |
| Statistics & Machine Learning Toolbox | 建議 | BADS 內部會用到 |
| Parallel Computing Toolbox + GPU | 可選 | 自動偵測,有 GPU 就走 GPU 路徑;沒有就 CPU,流程一致 |
| BADS toolbox | 已自帶 | 在 `bads-1.1.3/`,程式會自動 addpath |

不需要 Python、Jupyter,或任何外部依賴。

---

## 2. 三階段一條龍流程

```text
┌────────────────────────┐    ┌─────────────────────────────┐    ┌─────────────────────────┐
│ Stage 1: 理論 PSF 建立  │    │ Stage 2: Zernike 像差擬合    │    │ Stage 3: Wiener 反捲積  │
│ SimulatePSF/            │ ─▶ │ HDR_fitting_2D_WholeFOV.m   │ ─▶ │ HDR_fitting_2D_WholeFOV │
│ psf_multiwavelength_2D  │    │ (上半段:Stage 2 + 教學版    │    │ .m (下半段:Stage 3)    │
│ → psf_multi.mat         │    │ stack→single 銜接)          │    │ → deconv_result_2D.tiff │
└────────────────────────┘    └─────────────────────────────┘    └─────────────────────────┘
```

對應檔案:

```text
PSF_Fitting_Tutorial/
├── README_TW.md                                  ← 你正在讀的檔案
├── HDR_fitting_2D_WholeFOV.m                     ← 教學版主入口 (Stage 2 + Stage 3)
├── HDR_fitting_2D_WholeFOV_impl.m                ← Stage 2 實作
├── PSF_Fitting_ValidationLab/scripts/
│   ├── HDR_fitting_2D_WholeFOV_reasonable_v1.m   ← Stage 2 候選流程選擇器
│   ├── HDR_fitting_2D_WholeFOV_candidate_prealign.m  ← Stage 2 核心 (預對齊 + 14 維 Zernike + BADS)
│   └── vlab_translate_image.m                    ← 子像素位移
├── SimulatePSF/
│   ├── psf_multiwavelength_2D.m                  ← Stage 1 入口 (跨波長加權)
│   ├── MicroscPSF.m                              ← Gibson-Lanni 核心 (Bessel 級數)
│   ├── normlz.m                                  ← Min-Max 正規化
│   ├── spectrum.mat                              ← 光源光譜權重 (400-700nm)
│   └── psf_multi.mat                             ← 預跑好的 Stage 1 輸出 (可直接用)
├── Crop_circle_FreqFiltered/                     ← Stage 2 輸入
│   ├── VisionTop_..._N.bmp                       ← 100 張頻率濾波後的量測影像 (N = 1..100)
│   ├── GT/GT_901_with_Block_proc.bmp             ← Ground Truth (圓柱 BMP)
│   └── Fits/                                     ← Stage 2 輸出去處 (空)
├── Deconvolution/                                ← Stage 3 輸入 + 輸出
│   ├── GT/pillar_30_SEM.tiff                     ← SEM Ground Truth
│   ├── TestImages/30.tiff                        ← 待反捲積的實驗影像
│   ├── PSF/                                      ← 教學版自動把 stack 中代表 PSF 寫到這裡 (空)
│   └── Results/                                  ← Stage 3 輸出去處 (空)
└── bads-1.1.3/                                   ← BADS 全域最佳化 toolbox
```

---

## 3. 怎麼跑 (最快上手版)

開 MATLAB,把當前目錄切到 `PSF_Fitting_Tutorial/`,執行兩條指令:

```matlab
% 第一次跑時可以重新產生 Stage 1 (約 30 秒);如果不想重跑可以略過,直接用預跑好的 psf_multi.mat。
run('SimulatePSF/psf_multiwavelength_2D.m');

% Stage 2 + Stage 3 一氣呵成 (5 張 subset, 約 3-5 分鐘 CPU; 有 GPU 更快)
run('HDR_fitting_2D_WholeFOV.m');
```

跑完後產生:

| 路徑 | 內容 |
|---|---|
| `SimulatePSF/psf_multi.mat` | Stage 1 輸出:理論 PSF (101×101 double,sum-normalized) |
| `Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat` | Stage 2 輸出:4D PSF stack `[H W rows cols]` + 元資料 |
| `Crop_circle_FreqFiltered/Fits/batch_results.csv` | Stage 2 每張 FOV 的擬合摘要 (Zernike 係數、loss、迭代次數、預對齊位移) |
| `Crop_circle_FreqFiltered/Fits/formal_config.json` | Stage 2 的設定快照 |
| `Deconvolution/PSF/PSF_fitted_2D.mat` | 教學版自動從 stack 抽出的單張 PSF (R6C5 = FOV 55) |
| `Deconvolution/Results/deconv_result_2D.tiff` | Stage 3 輸出:Wiener 反捲積結果 (16-bit tiff) |

跑完還會跳出兩張 figure:Stage 3 的反捲積結果預覽,以及 Stage 2 過程中的 loss 收斂圖。

---

## 4. 階段 1 — Gibson-Lanni 理論 PSF 建立

### 4.1 為什麼需要這一步

Stage 2 的 PSF 擬合不是「從零開始」 — 它是「在一個物理上合理的基底 PSF 上,加上 Zernike 像差擾動」。基底 PSF 必須符合系統的數值孔徑、波長、放大率等實際參數,否則擬合空間就偏離合理區間。

Gibson-Lanni (1992) 模型是顯微鏡 PSF 計算的標準分析模型,把光學系統的物理參數 (NA, 波長, 折射率, 工作距離, 蓋玻片厚度...) 對應到 PSF 的形狀。本教學使用 Li, Xue & Blu (2017) 的快速 Bessel 級數實作。

### 4.2 主要程式檔

`SimulatePSF/psf_multiwavelength_2D.m`(入口,30 行)做的事:

1. 讀取光源光譜 `spectrum.mat`(400-700 nm 的能量分布)。
2. 對每個波長呼叫 `MicroscPSF.m` 算單波長 PSF (此教學設定 j=580,即 580 nm,只算一個波長,可改成 for loop 跨 400-700nm 加權積分)。
3. 用光譜權重把多波長 PSF 加總成一張 2D 多波長 PSF。
4. 對總能量歸一化 (`sum=1`),存成 `psf_multi.mat`。

`SimulatePSF/MicroscPSF.m`(Gibson-Lanni 核心)是 Li/Xue/Blu 的官方實作 (約 210 行):

- 用 Bessel 級數 (Bessel 函數線性組合) 近似 `exp(iW)` 中的相位項 W (光程差 OPD)。
- 用 100 個 basis function、1000 個 sampling 點求出近似係數。
- 軸向以 `Ti = ti0 + resAxial × (z - z_center)` 取多個切片;本 2D 教學只取 1 個切片 (`size = [101 101 1]`)。

### 4.3 主要參數速查 (`psf_multiwavelength_2D.m` 內)

| 參數 | 教學版預設 | 物理意義 | 改變影響 |
|---|---|---|---|
| `param.size` | `[101 101 1]` | PSF 像素尺寸 (3D 才用 z) | 越大計算越慢,2D 教學用 101×101 |
| `param.NA` | `0.23` | 顯微鏡的數值孔徑 | NA 越大,PSF 越窄 (繞射極限越小) |
| `param.lambda` | `580e-9` (m) | 光源波長 | 波長越短,PSF 越窄 |
| `param.M` | `20` | 鏡頭放大率 | 不影響 PSF 形狀,只影響像素尺寸對應 |
| `param.resLateral` | `0.125 × 1e-6` (m) | 影像感測器的橫向像素尺寸 | 直接影響 PSF 採樣密度 |
| `param.resAxial` | `74e-9` (m) | z 方向像素尺寸 | 2D 教學只取單張切片,沒實際影響 |
| `param.tg`, `param.tg0` | `0`, `0` | 蓋玻片實際/設計厚度 | 不一致時會引入 spherical aberration |
| `param.ng`, `param.ng0` | `1`, `1` | 蓋玻片折射率 (實際/設計) | 不一致時會引入像差 |
| `param.ni`, `param.ni0` | `1`, `1` | 浸潤介質折射率 | 與 NA 共同決定可達到的最大孔徑角 |
| `param.ti0` | `1e-3` (m) | 工作距離 | 與 resAxial 一起決定 z 切片位置 |
| `param.pZ` | `0` | 螢光珠 z 偏移 | 設計用來算離焦 PSF;此教學用 0 (在焦) |

注意這份教學的設定是針對特定產學專案的光學系統參數(沒有蓋玻片、空氣折射率、580 nm 主波長、NA 0.23、橫向像素 0.125 µm)。**如果要套用到別的系統**,主要就是改這些 `param.*`。改完重跑 `psf_multiwavelength_2D.m` 即可重新產生 `psf_multi.mat`。

### 4.4 想跨波長積分

把 `for j = 580:580` 改成 `for j = 400:700`(`spectrum.mat` 涵蓋 400-700nm 共 301 個取樣點),程式會自動對所有波長加權積分。改完一張 PSF 大約多花 100 倍時間 (101 vs 1 個波長),但形狀會更貼近寬頻光源的實際 PSF。

### 4.5 輸出

`SimulatePSF/psf_multi.mat`,變數名 `psf_multi`,大小 `101×101`,double,`sum(psf_multi(:)) = 1`。

教學包已經提供預跑好的版本,使用者可以直接跳過 Stage 1 進入 Stage 2。

---

## 5. 階段 2 — Zernike 像差參數化擬合 (Whole-FOV)

### 5.1 為什麼用 Zernike

理論 PSF 假設光學系統「無像差、完美對焦」。實際拍出來的 PSF 永遠帶有像差(離焦、像散、彗差、球差……),而像差有一個漂亮的數學工具就是 Zernike 多項式 — 它在單位圓盤上正交,前 14 項剛好涵蓋了所有實務中重要的像差類型:

| Z 編號 (Noll) | 名稱 | 物理意義 |
|---|---|---|
| Z1, Z2 | tip / tilt | 整體偏移 (子像素位移補償) |
| Z3 | astigmatism (45°) | 像散,45° 軸 |
| Z4 | defocus | 離焦 |
| Z5 | astigmatism (0°) | 像散,0° 軸 |
| Z6, Z7 | trefoil | 三角像差 |
| Z8, Z9 | coma (y/x) | 彗差,y/x 軸 |
| Z10, Z11 | tetrafoil | 四角像差 |
| Z12 | spherical | 球差 |
| Z13, Z14 | secondary astigmatism | 高階像散 |

擬合時只要找出 14 個 Zernike 係數 + 1 個振幅修正,就能把無像差基底 PSF 「彎曲」成最貼近真實量測的形狀。比起直接擬合 PSF 像素值 (數萬個自由度) 或擬合單純 Gaussian (3 個自由度),Zernike 的 14+1 維剛好是「物理意義豐富但仍可全域搜尋」的甜蜜點。

### 5.2 為什麼用 BADS

14+1 維 + 影像級損失函數,通常會有多個 local minima。L-BFGS / fminunc 等梯度下降法很容易卡在第一個落腳處;直接做 grid search 又算不完。BADS (Acerbi & Ma, 2017) 用「貝氏代理模型 + 自適應方向直接搜尋」混合策略,在 ~50 維以下、計算成本中等的問題表現很好,實務上能跳出大部分 local minima。

教學包自帶的 `bads-1.1.3/` 是上游官方版本,沒有改動。

### 5.3 損失函數

`HDR_fitting_2D_WholeFOV_candidate_prealign.m` 中的 `candidate_aberration_loss`:

```matlab
loss = 1 × MSE(freq_loss) + 2×10^4 × MSE(grad_loss)
```

- **freq_loss**:模擬影像 (`GT * fitted_psf` 卷積) vs 量測影像,在頻域上比較。低頻 (DC) 跟過高頻段 (>50% Nyquist) 用 mask 屏蔽,只比中頻段。
- **grad_loss**:模擬影像 vs 量測影像,各自做梯度後 min-max 正規化,再算 MSE。

加權 `2×10^4` 是經驗值,這個權重讓兩個 loss 在數值上量級接近。改這個權重會讓擬合偏向 freq 或 grad 中的某一邊。

### 5.4 預對齊

擬合前會先做整數 + 子像素位移搜尋,讓量測影像對齊 GT。搜尋範圍 ±2 像素,步進 0.25 像素,以梯度圖的 NCC (Normalized Cross-Correlation) 為對齊判據。對齊後再進入 BADS 擬合。沒對齊好會讓擬合 PSF 把位移當成像差吃掉,得到形狀變形的 PSF。

### 5.5 變數範圍 (lb / ub)

教學版預設 (`HDR_fitting_2D_WholeFOV_candidate_prealign.m` line 134-136):

```matlab
x0 = [0 0 0 0 0 0 0 0 0 0 0 0 0 0 1.0]                               % 14 個 Zernike + 1 個振幅
lb = [-0.3 -0.3 -0.1 0   -0.1 -0.05 -0.05 -0.05 -0.05 -0.01 -0.01 0   -0.01 -0.01 0.8]
ub = [ 0.3  0.3  0.1 1.0  0.1  0.05  0.05  0.05  0.05  0.01  0.01 0.3  0.01  0.01 1.25]
```

低階 Zernike (Z1-Z5) 給比較大的搜尋空間 (±0.3 / ±0.1),高階 Zernike (Z10+) 收緊 (±0.01)。這反映「實際系統像差以低階為主」的物理事實 —— 給高階太大的空間會讓擬合過度配適。

### 5.6 Whole-FOV vs subset

正式版預設跑全 100 張 (`subset_indices = 1:100`),本教學包預設只跑 5 張代表性 FOV (4 角 + 中心):

```matlab
tutorial_subset = [1 10 55 91 100];   % 在 HDR_fitting_2D_WholeFOV.m line 22
```

**對照表 (10×10 FOV grid,row-major):**

| FOV 編號 | (row, col) | 位置含義 |
|---|---|---|
| 1 | (1, 1) | 左上角 |
| 10 | (1, 10) | 右上角 |
| 55 | (6, 5) | 接近中心 |
| 91 | (10, 1) | 左下角 |
| 100 | (10, 10) | 右下角 |

想跑別張或全 FOV,改 `tutorial_subset`。例如:

```matlab
tutorial_subset = 1:100;       % 跑全 FOV (約 30 分鐘到 1 小時)
tutorial_subset = 55;          % 只跑中心 FOV
tutorial_subset = 1:10:100;    % 跑第一列 (FOV 1, 11, 21, ..., 91)
tutorial_subset = [25 50 75];  % 任意指定
```

Stage 2 內部還是建立 `[H W 10 10]` 的 4D stack,沒被擬合的位置以 0 填充。

### 5.7 Warm start

預設 `warm_start = true`:每張 FOV 從上一張的最佳 Zernike 係數出發,而不是從零。在連續 FOV 像差變化緩慢的情況下能加速收斂。

### 5.8 輸出

| 檔名 | 內容 |
|---|---|
| `Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat` | 4D PSF stack `psf_grid`,大小 `[101 101 10 10]`;另含 `coef_grid [15 10 10]`、`fval_map`、`iterations_map`、`filename_map` 等 |
| `Crop_circle_FreqFiltered/Fits/batch_results.csv` | 每張 FOV 的擬合摘要 (Zernike 係數展開、loss、迭代次數、預對齊位移、PSF peak/centroid 位置) |
| `Crop_circle_FreqFiltered/Fits/formal_config.json` | Stage 2 設定快照 (subset 範圍、warm_start、lock_tilt 等) |

---

## 6. 階段 3 — Wiener 反捲積驗證

### 6.1 思路

Stage 2 擬合出的 PSF 究竟好不好用?最直接的驗證方式是拿它去做反捲積 — 如果反捲積結果跟 SEM Ground Truth 很接近,就代表擬合到的 PSF 抓對了系統的真實退化形狀。

Wiener 反捲積:

```text
Img_d(f) = (PSF*(f) / (|PSF(f)|^2 + NSR)) × Img(f)
```

NSR (Noise-to-Signal Ratio) 是一個正則化項,避免 |PSF|^2 接近 0 的頻段把雜訊放大。NSR 太小 → 雜訊爆炸;NSR 太大 → 過度平滑。

教學版用 BADS 在 NSR 的 log-scale 上 (lb=1e-3, ub=1e3) 搜尋,目標是讓「反捲積結果的梯度」貼近「SEM GT 的梯度」。

### 6.2 從 stack 抽單張 PSF

`HDR_fitting_2D_WholeFOV.m` 的 Stage 2 → Stage 3 銜接區塊 (教學版加的):

```matlab
picked_row = 6;   picked_col = 5;     % 預設抽 R6C5 = FOV 55
fitted_psf = stack_data.psf_grid(:, :, picked_row, picked_col);
```

抽出後寫到 `Deconvolution/PSF/PSF_fitted_2D.mat`,Stage 3 直接 load。如果指定的 (row, col) 不在 subset 內 (擬合結果為 0),會 fallback 抽 subset 中第一張成功擬合的 FOV。

**正式版差異**:正式版要使用者自己用 MATLAB 變數瀏覽器或腳本從 4D stack 挑出代表性 PSF、改名為 `PSF_fitted_2D.mat`、搬到 `Deconvolution/PSF/`,過程沒自動化。

### 6.3 NSR 搜尋

```matlab
[x, fval] = bads(@wnrbads, 1, 1e-3, 1e3);   % x0=1, lb=1e-3, ub=1e3
img_d = deconvwnr(img, psf, x);
```

`wnrbads` 損失函數: `100 × MSE(grad(deconv), grad(GT))`,只看梯度差,不看絕對亮度差。這在反捲積邊緣銳利度上比較敏感。

### 6.4 輸出

| 檔名 | 內容 |
|---|---|
| `Deconvolution/Results/deconv_result_2D.tiff` | 16-bit 反捲積結果影像 |

跑完還會跳出 figure 顯示:原始 / 反捲積 / 使用的 PSF / 反捲積與 GT 之差。

---

## 7. 重要參數對照表 (一張表全收)

| 階段 | 檔案 | 行號 | 參數 | 預設 | 改動建議 |
|---|---|---|---|---|---|
| 1 | `psf_multiwavelength_2D.m` | 5 | `for j = 580:580` | 單波長 580nm | 改成 `400:700` 跨波長加權 |
| 1 | `psf_multiwavelength_2D.m` | 7 | `param.NA` | 0.23 | 換系統時必改 |
| 1 | `psf_multiwavelength_2D.m` | 10 | `param.resLateral` | 0.125 µm | 換相機時必改 |
| 2 | `HDR_fitting_2D_WholeFOV.m` | 22 | `tutorial_subset` | `[1 10 55 91 100]` | 改 1:100 跑全 FOV |
| 2 | `candidate_prealign.m` | 134-136 | `x0 / lb / ub` | 見 5.5 | 系統像差量級不同時要重設 |
| 2 | `candidate_prealign.m` | 58 | `prealign_search_radius` | 2 | 預對齊像素搜尋半徑 |
| 2 | `candidate_prealign.m` | 60 | `prealign_search_step` | 0.25 | 預對齊步進 (子像素) |
| 2 | `candidate_prealign.m` | 61 | `prealign_crop_size` | 257 | 預對齊用的中心裁切大小 |
| 3 | `HDR_fitting_2D_WholeFOV.m` | 38-39 | `picked_row / picked_col` | 6, 5 (中心) | 改成想用的 FOV 位置 |
| 3 | `HDR_fitting_2D_WholeFOV.m` | 80-82 | `x0 / lb / ub` for NSR | 1, 1e-3, 1e3 | NSR log-scale 搜尋範圍 |

---

## 8. 換成自己的資料

要把這個教學包套用到自己的影像,有三個層級的替換:

### 8.1 只換量測影像 (光學系統一樣)

把新的 100 張頻率濾波後 BMP 放進 `Crop_circle_FreqFiltered/`,檔名格式維持 `VisionTop_<時間戳>_<index>.bmp`,index 從 1 到 100 對應 10×10 FOV grid (row-major, 1=R1C1, 10=R1C10, 11=R2C1, ..., 100=R10C10)。

把 GT 換成 `Crop_circle_FreqFiltered/GT/GT_901_with_Block_proc.bmp` (檔名要一致,或修改 `candidate_prealign.m` 中的路徑)。

### 8.2 換光學系統 (NA / 波長 / 像素尺寸不同)

修改 `SimulatePSF/psf_multiwavelength_2D.m` 中的 `param.*` 參數,重跑 Stage 1 產生新的 `psf_multi.mat`。

如果系統像差量級跟原系統差很多,可能還要調 `candidate_prealign.m` line 134-136 的 Zernike 變數範圍 `lb / ub`。範圍太窄會把像差「截斷」;太寬會讓擬合過度配適。

### 8.3 換 FOV grid 大小 (不是 10×10)

修改 `HDR_fitting_2D_WholeFOV_impl.m` 呼叫處傳入 `'grid_rows'`, `'grid_cols'` 參數。`HDR_fitting_2D_WholeFOV_candidate_prealign.m` 內部的 `floor((fi-1)/10)+1` 跟 `mod(fi-1,10)+1` 也要對應改 (假設 `grid_cols = 10`)。

### 8.4 想跑別張或全張

只要改 `HDR_fitting_2D_WholeFOV.m` line 22 的 `tutorial_subset`:

```matlab
tutorial_subset = 1:100;    % 跑全 FOV (~30-60 分鐘 CPU)
tutorial_subset = 55;       % 只跑中心
tutorial_subset = 1:5:100;  % 每 5 張取一張 (20 張)
```

如果改了 subset 不再涵蓋預設位置 R6C5 (FOV 55),Stage 2 → 3 銜接會自動 fallback 到 subset 中第一張成功擬合的 FOV。如果想指定別的 FOV 做反捲積,改 line 38-39 的 `picked_row` / `picked_col`。

---

## 9. 常見問題排錯

### Q1. `Undefined function or variable 'bads'`

BADS 沒在 path 上。檢查 `bads-1.1.3/` 是否存在於教學包根目錄。`HDR_fitting_2D_WholeFOV.m` 的 Stage 3 區塊 (line 65) 會自動 addpath,但如果你只跑 Stage 2 就遇到,可能是 `candidate_prealign.m` line 15 的相對路徑解析失敗 — 確認你的 working directory 是 `PSF_Fitting_Tutorial/` 而不是其他地方。

### Q2. `Undefined function or variable 'psf_multi'`

`psf_multi.mat` 沒讀到。檢查 `SimulatePSF/psf_multi.mat` 是否存在;沒有的話跑一次 `run('SimulatePSF/psf_multiwavelength_2D.m')`。

### Q3. `Index in position 1 exceeds array bounds`

通常是 `subset_indices` 超出 `Crop_circle_FreqFiltered/` 中實際 BMP 數量。教學包提供 100 張,所以 `subset_indices` 必須在 `1..100`。如果你只放了部分 BMP,要對應縮小 subset。

### Q4. GPU OOM / `gpuArray` 錯誤

GPU VRAM 不夠或驅動異常。可以強制走 CPU:

```matlab
summary = HDR_fitting_2D_WholeFOV_impl('subset_indices', tutorial_subset, 'use_gpu', false);
```

### Q5. Stage 3 反捲積結果一片黑/一片白

通常是 NSR 搜尋陷入極端值。檢查 `Deconvolution/PSF/PSF_fitted_2D.mat` 的內容是不是合理 (`sum(psf(:)) ≈ 1`,且 PSF 峰值在中心附近)。如果 PSF 形狀崩壞,可能 Stage 2 擬合沒收斂 — 看 `batch_results.csv` 的 `iterations` 跟 `fval` 欄位確認該 FOV 是否合理。

### Q6. 跑很慢

Stage 2 全 100 張 CPU 會跑 30 分鐘到 1 小時。教學版預設 5 張 subset 大約 3-5 分鐘 (CPU)。如果還是太慢:
- 確認 BADS toolbox 載入正確 (path 設定)
- 開 GPU (`use_gpu` 預設自動偵測,有 CUDA + Parallel Computing Toolbox 就會用)
- 縮小 subset 到 1 張先驗證流程

### Q7. 想看擬合過程的 loss 曲線

預設沒有自動畫 (避免 GUI 拖慢執行)。要看的話可以打開 `candidate_prealign.m`,修改 `candidate_aberration_loss` 在每幾次 iteration 加 `figure / plot loss_history`。或者跑完後從 `batch_results.csv` 後處理。

---

## 10. 怎麼打包丟給別人

直接把整個 `PSF_Fitting_Tutorial/` 資料夾壓縮成 zip:

```powershell
Compress-Archive -Path PSF_Fitting_Tutorial -DestinationPath PSF_Fitting_Tutorial.zip
```

預期壓縮後約 60-80 MB (主要是 100 張 BMP)。接收者解壓後,在 MATLAB 切到 `PSF_Fitting_Tutorial/` 為 working directory,執行 `run('HDR_fitting_2D_WholeFOV.m')` 就能從 Stage 2 跑到 Stage 3。Stage 1 因為已預跑可略過。

---

## 11. 附錄

### 11.1 Gibson-Lanni 公式速覽

PSF 在像平面上的場分佈:

```text
h(x, y) = | ∫₀^α  exp(i × W(ρ)) × J₀(k × NA × ρ × r) × ρ dρ |²
```

- `α = arcsin(NA / n_immersion)`:最大孔徑角
- `W(ρ)`:光程差 (Optical Path Difference),含 4 項主要貢獻 (sample, immersion, coverslip, objective)
- `J₀`:第一類零階 Bessel 函數
- `r = √(x² + y²)`:像平面上到光軸的距離

Li-Xue-Blu (2017) 的快速演算法把 `exp(iW(ρ))` 用 N 個 Bessel 函數的線性組合近似 (`exp(iW(ρ)) ≈ Σ cᵢ J₀(aᵢρ)`),這樣徑向積分可以用 Bessel 函數的解析積分公式做,不需要數值積分,速度提升 50-100 倍。

### 11.2 Zernike 多項式 (Noll 1976 編號)

教學中使用的 14 項:

```text
Z1  = 2ρ sin(φ)                              tilt y
Z2  = 2ρ cos(φ)                              tilt x
Z3  = √6 × ρ² sin(2φ)                        astigmatism 45°
Z4  = √3 × (2ρ² - 1)                         defocus
Z5  = √6 × ρ² cos(2φ)                        astigmatism 0°
Z6  = √8 × ρ³ sin(3φ)                        trefoil
Z7  = √8 × (3ρ³ - 2ρ) sin(φ)                 coma y
Z8  = √8 × (3ρ³ - 2ρ) cos(φ)                 coma x
Z9  = √8 × ρ³ cos(3φ)                        trefoil
Z10 = √10 × ρ⁴ sin(4φ)                       tetrafoil
Z11 = √10 × (4ρ⁴ - 3ρ²) sin(2φ)              secondary astigmatism 45°
Z12 = √5  × (6ρ⁴ - 6ρ² + 1)                  primary spherical
Z13 = √10 × (4ρ⁴ - 3ρ²) cos(2φ)              secondary astigmatism 0°
Z14 = √10 × ρ⁴ cos(4φ)                       tetrafoil
```

ρ = 半徑 (歸一化到 [0,1]),φ = 方位角。

### 11.3 引用文獻

1. Gibson, S.F. & Lanni, F. (1992). Experimental test of an analytical model of aberration in an oil-immersion objective lens used in three-dimensional light microscopy. *JOSA A*, **9**(1), pp.154-166.
2. Li, J., Xue, F. & Blu, T. (2017). Fast and accurate 3D PSF computation for fluorescence microscopy. *J. Opt. Soc. Am. A*, **34**(6), pp.1029-1034.
3. Acerbi, L. & Ma, W.J. (2017). Practical Bayesian Optimization for Model Fitting with Bayesian Adaptive Direct Search. *Advances in Neural Information Processing Systems* 30 (NIPS 2017).
4. Noll, R.J. (1976). Zernike polynomials and atmospheric turbulence. *JOSA*, **66**(3), pp.207-211.
5. PSFgenerator (BIG, EPFL): http://bigwww.epfl.ch/algorithms/psfgenerator/

### 11.4 與正式版的差異一覽

| 項目 | 正式版 (`PSF_Fitting/`) | 教學版 (`PSF_Fitting_Tutorial/`) |
|---|---|---|
| Stage 1 入口 | `SimulatePSF/psf_multiwavelength_2D.m` | 一字不改,複製過來 |
| Stage 2 + 3 入口 | `HDR_fitting_2D_WholeFOV.m` (跑全 100 張、Stage 2/3 之間需手動搬檔) | 加 `tutorial_subset` 參數 + 自動 stack→single 銜接 |
| Stage 2 實作 | `HDR_fitting_2D_WholeFOV_impl.m` | 一字不改 |
| ValidationLab 相依 | 整個 `PSF_Fitting_ValidationLab/` (~17 MB,含驗證、報告、圖表) | 只挑出 Stage 2 真正用到的 3 支 .m (`reasonable_v1`, `candidate_prealign`, `vlab_translate_image`) |
| BADS toolbox | 在 repo 根目錄 `bads-1.1.3/` | 同樣自帶 |
| 輸入影像 | `Crop_circle_FreqFiltered/` 100 張 | 同樣 100 張 (完整搬過來) |
| 反捲積輸入 | `Deconvolution/GT/`, `Deconvolution/TestImages/` | 同樣搬過來 |
| 預跑成果 | (不附) | 自帶 `psf_multi.mat`,讓使用者可略過 Stage 1 |

教學版的所有差異都是「讓教學一氣呵成、降低執行門檻」,沒有改變任何擬合邏輯或物理模型。
