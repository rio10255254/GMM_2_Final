# Validation Experiments — PSF 快速校正方法的算法驗證實驗

> **子專案目的**：用實驗校準 [`DESIGN_TW.md`](../DESIGN_TW.md) 提出的階梯校正方法的所有閾值與 noise floor，
> 證明該方法在「同一台機台拆裝」場景下可行,作為跨機部署前的算法 acceptance gate。
>
> **建立日期**：2026-05-05
> **跟誰隔開**：本子專案是「**新方法**」的算法驗證,跟 `PSF_Fitting/PSF_Fitting_ValidationLab/`(現行流程的歷史比較沙盒)是兩件不同的事,不要混淆。
> **參考主文件**：[`../DESIGN_TW.md`](../DESIGN_TW.md) §10 (算法驗證實驗 A 階段)

---

## 目錄

1. [這個子專案在驗證什麼](#1-這個子專案在驗證什麼)
2. [跟 ValidationLab 的差異(很容易搞混,先講清楚)](#2-跟-validationlab-的差異很容易搞混先講清楚)
3. [四層實驗總覽](#3-四層實驗總覽)
4. [目前實作狀態](#4-目前實作狀態)
5. [目錄結構](#5-目錄結構)
6. [共用前提與依賴](#6-共用前提與依賴)
7. [污染控制清單(全實驗共用)](#7-污染控制清單全實驗共用)

---

## 1. 這個子專案在驗證什麼

DESIGN 文件提出的階梯校正方法 (L0–L4) 裡,所有「該升級到下一級」的門檻,
例如 z-score > 3、殘差 > 模板基準 × 1.5、median |z| < 2 才算沒變,
都是設計階段**用合理推測訂出來的**,沒有實證基礎。

本子專案做的事就是 **用實驗把這些猜的數字換成量出來的數字**:

- **校準 noise floor**:BADS 演算法本身的隨機性、拍攝噪聲到底有多大
- **校準階梯升級閾值**:在「沒動」跟「真動」之間找到正確的判決門檻
- **驗證歸因方法的準確率**:Test 1/2/3 三層測試能不能正確分辨「擬合雜訊 vs 真實機台變化」

實驗的巧妙之處:目前手邊只有一台機,沒辦法直接跨機驗證,
所以 **用「同一台機反覆拆裝」當作「假裝是另一台機」**——只動物鏡安裝公差這一個變數,
讓變數隔離乾淨。

---

## 2. 跟 ValidationLab 的差異(很容易搞混,先講清楚)

| | `PSF_Fitting_ValidationLab/` | 本子專案 `validation_experiments/` |
|---|---|---|
| 驗證對象 | **現行** Whole-FOV 流程的修正(例如 pre-alignment fix) | **新提案** 的快速校正方法 |
| 用什麼資料 | 現有的 100 張 raw + GT | 同樣的 100 張 raw + GT,但會 **新增拆裝後重拍的影像** |
| 寫的是什麼 fitter | 現行 fitter 的對照組(例如 reasonable_v1) | 復用現行 fitter,**不寫新 fitter**,只寫「重複呼叫」與「分析」的腳本 |
| 結果用在哪 | PSF 政策決策(例如要不要 promote 到正式標準) | 算法 acceptance gate(例如閾值校準、是否上線新方法) |

**簡單講**:ValidationLab 是「**修舊**」,這裡是「**驗新**」。

---

## 3. 四層實驗總覽

| 層 | 動作 | 重複次數 | 拍攝介入 | 對應的判決校準 | 估計時間 |
|---|---|---|---|---|---|
| **L0** | 同一張影像,BADS 跑 N 次 | 5 | 不重拍(用既有影像) | Test 1 的 noise floor 下界(純演算法隨機性) | 45–90 分(9 個 FOV 點 × 5 trials) |
| **L1** | 同機台不動,**重新拍** 100 張 | 3 | 重拍 ×3,中間不碰機台 | Test 1 的 noise floor 上界(拍攝噪聲) | 1.5–2 hr/次 × 3 次 = 4.5–6 hr |
| **L2** | 假介入(關機重開、輕碰外殼,**不拆**) | 2 | 介入後重拍 ×2 | 階梯不該被誤判升級(false positive rate) | 同 L1 規模 ×2 |
| **L3** | 真介入(拆裝物鏡) | 3–5 | 拆裝後重拍 ×3–5 | 階梯應正確識別(true positive rate)+ 模態歸因正確性 | 同 L1 規模 ×3–5 |

**為什麼這樣排**:從「完全沒動」一路加重到「真的拆」,看新方法的偵測系統什麼時候才開始亮燈。

詳細實驗設計、acceptance criteria、污染控制原則:見 [`../DESIGN_TW.md`](../DESIGN_TW.md) §10。

---

## 4. 目前實作狀態

| 實驗 | 狀態 | 子目錄 |
|---|---|---|
| L0 repeat fit | **已實作,未執行** | [`L0_repeat_fit/`](L0_repeat_fit/) |
| L1 repeat capture | 未實作 | — |
| L2 pseudo intervention | 未實作 | — |
| L3 real disassembly | 未實作 | — |

L1–L3 等 L0 跑完、noise floor 校準完、`L0_repeat_fit/L0_noise_floor_report.md` 產出後再開。
不要先開空目錄。

---

## 5. 目錄結構

```
validation_experiments/
├── README_TW.md                            ← 本檔
├── .gitignore                              ← 排除 outputs/(.mat 太大)
└── L0_repeat_fit/                          ← L0 已實作
    ├── README_TW.md                        ← L0 細節
    ├── run_L0_repeat_fit.m                 ← MATLAB 入口
    ├── analyze_L0_noise_floor.py           ← Python 分析
    └── outputs/                            ← 執行時自動建立(gitignore)
        ├── trial_01/
        │   ├── batch_results.csv
        │   ├── PSF_fitted_2D_FOVstack.mat   ← coef_grid (15×1×N), subset-order
        │   ├── candidate_config.json
        │   └── reasonable_config.json
        ├── trial_02/ ...
        ├── manifest.json                   ← 此次執行的選擇紀錄
        └── L0_noise_floor_report.md        ← 分析腳本輸出
```

---

## 6. 共用前提與依賴

所有實驗都依賴下面這些既有資源,**本子專案不複製、不修改它們**:

| 資源 | 路徑 | 用途 |
|---|---|---|
| BADS 擬合核心 | `PSF_Fitting/PSF_Fitting_ValidationLab/scripts/HDR_fitting_2D_WholeFOV_candidate_prealign.m` | 真正在跑 BADS 的地方 |
| 包裝入口 | `PSF_Fitting/HDR_fitting_2D_WholeFOV_impl.m` | 一行就能呼叫,自動處理 output |
| 種子機影像 | `PSF_Fitting/Crop_circle_FreqFiltered/VisionTop_*.bmp` | L0 用既有 100 張;L1–L3 會重拍 |
| GT | `PSF_Fitting/Crop_circle_FreqFiltered/GT/GT_901_with_Block_proc.bmp` | 通用 |
| 理論 PSF 基底 | `PSF_Fitting/SimulatePSF/psf_multi.mat` | 通用 |
| BADS 套件 | `PSF_Fitting/bads-1.1.3/` | 已 addpath |

**MATLAB Current Folder 必須設為 `d:\GMM_2_Final\PSF_Fitting\`**(同 `PSF_Fitting/README.md` §使用前準備)。

---

## 7. 污染控制清單(全實驗共用)

DESIGN §10.5 的污染控制原則,提出來放這裡讓所有後續實驗都看得到:

| 不要做 | 為什麼會污染 |
|---|---|
| 拆裝中順便清鏡頭 | 變兩個變數 |
| 換不同物鏡 | 變數從一個變成兩個,而且更大 |
| 中間移動 GT 樣本 | 影像位置變,Zernike 中心被吃掉 |
| 一天做不完拖到隔天 | 室溫差 5°C 足以造成可量測的 PSF 漂移 |
| L3 拆裝交給不同人 | 操作差異混入 |

**核心精神**:只動一個變數,其他全部凍結。
