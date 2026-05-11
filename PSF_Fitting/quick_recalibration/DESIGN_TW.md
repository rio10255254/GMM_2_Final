# 同型號光機 PSF 快速校正流程 — 設計思路文件

> **文件狀態**:設計階段(brainstorming 產物),**尚未實作**。
> 實作前需通過 user review,並進入正式的 implementation plan(writing-plans)。
>
> **建立日期**:2026-04-18
> **適用範疇**:同型號(等級 2)— 相同光路設計、相同元件規格、僅有個體公差差異的光機
> **作者**:Rio + Claude(brainstorming session)
> **參考主文件**:
> - [`PSF_Fitting/README.md`](../README.md)
> - [`PROJECT_STATE.md`](../../PROJECT_STATE.md)
> - [`docs/policy/PSF_POLICY_TRANSITION_R26.md`](../../docs/policy/PSF_POLICY_TRANSITION_R26.md)

---

## 目錄

1. [文件目的與閱讀對象](#1-文件目的與閱讀對象)
2. [問題陳述](#2-問題陳述)
3. [設計範疇與假設](#3-設計範疇與假設)
4. [核心想法(整體哲學)](#4-核心想法整體哲學)
5. [系統架構總覽](#5-系統架構總覽)
6. [機型模板的詳細規格](#6-機型模板的詳細規格)
7. [快速校正階梯的詳細規格](#7-快速校正階梯的詳細規格)
8. [機型模板的三個成熟階段](#8-機型模板的三個成熟階段)
9. [誤差歸因方法](#9-誤差歸因方法)
10. [算法驗證實驗(A 階段)](#10-算法驗證實驗a-階段)
11. [與現有系統的整合](#11-與現有系統的整合)
12. [建議的檔案結構](#12-建議的檔案結構)
13. [實施路線圖](#13-實施路線圖)
14. [開放問題與未來擴充](#14-開放問題與未來擴充)
15. [附錄:術語對照與設計決策紀錄](#15-附錄術語對照與設計決策紀錄)

---

## 1. 文件目的與閱讀對象

### 1.1 為什麼有這份文件

`PSF_Fitting/` 模組目前的正式工作流程是 `HDR_fitting_2D_WholeFOV.m` —
對 100 張 FOV 影像從**零像差初始值**開始 BADS 擬合,完整跑一輪約 1.5–2 小時。
這個流程適合「研究階段」(同一台種子機的 PSF 從無到有建立),
但**不適合**以下兩個未來會發生的場景:

1. **同一台光機被拆裝過(例如更換、清潔、重對焦物鏡)後的快速重校**
   — 機台大致相同,只有少量像差項漂移,不應該每次都從零跑。
2. **同一型號的不同台機台之間的校正轉移(本份文件主要場景)**
   — 不同台量產機光路設計相同,只有個體公差差異,應該能用「機型先驗」加速。

本文件的目的是 **針對第 2 個場景**,提出一套:
- **新方法**:用「機型 reference PSF」當先驗的階梯式校正流程
- **驗證方法**:能在實驗室一台機(透過拆裝物鏡介入)就驗證該方法可行性的實驗設計
- **誤差歸因方法**:能區分「BADS 擬合本身的不確定性」、「拍攝噪聲」、與「機台真實變化」三個來源

### 1.2 閱讀對象

| 角色 | 看哪些章節 |
|---|---|
| 想知道整體想法的人(包含未來的 Rio 自己) | §1, §2, §4, §5, §13 |
| 想實作的人 | §6, §7, §8, §11, §12 |
| 想驗證新方法的人 | §9, §10 |
| 想評估治理風險的人 | §3, §8.4, §14 |

### 1.3 這份文件**不是**什麼

- **不是 implementation plan**(那是 writing-plans 的下一步產物)
- **不是 review 紀錄**(實驗結果與 review 應另開檔案)
- **不是論文**(論文章節要符合「論文與產學邊界」原則,不含具體機台/數據)

---

## 2. 問題陳述

### 2.1 現行流程的真實成本

以 `Crop_circle_FreqFiltered/` 的 100 張全 FOV 為例:

| 階段 | 動作 | 時間估計 |
|---|---|---|
| 拍攝 | 觸發拍 100 張 BMP | 10–30 分鐘(含 stage 移動) |
| 預處理 | 頻率濾波 | 5–10 分鐘 |
| Pre-alignment | refined raw/GT 對齊 | 5 分鐘 |
| **BADS 擬合** | 100 張依序擬合(warm-start 開) | **1.5–2 小時(GPU 開)** |
| Post-process | 寫 batch_results.csv、視覺化 | 5 分鐘 |

**核心瓶頸是 BADS 擬合的 1.5–2 小時。** 之所以慢,是因為:
- 每張影像跑 200–400 iterations,每 iteration 含一次 PSF 構造 + FFT-based forward sim + gradient loss
- 100 張影像要連續跑(雖然 warm-start 加速,但仍是線性累加)
- BADS 是 mesh-based + Gaussian Process surrogate,不是純梯度法,iteration 個別成本高

### 2.2 為什麼這個成本對「同型號量產校正」是不可接受的

假設未來要 deploy 到 N 台同型號機台(例如 10 台產線):
- N=10 → 純擬合時間 = 15–20 小時(2 個工作天)
- 還沒算 N+1 台時若機型有版本更新,要全部重跑

這個成本在以下情境會出問題:
- **產線交機驗收**:每台都要做 PSF 校正,排程被拖垮
- **機台保養後重校**:保養完不能立即上線,要等隔夜
- **跨地點部署**:每個 site 都要自己跑一次完整流程

### 2.3 新方法的目標

| 指標 | 現行流程 | 新方法目標 |
|---|---|---|
| 單台機完整校正時間 | 1.5–2 小時 | **5–15 分鐘**(L1 / L2 階梯停下時) |
| 校正後 PSF 的精度損失 | (基準) | < 5%(用反捲積結果與 SEM GT 的對比衡量) |
| 校正完成後能不能說明「為什麼這台跟標準有差」 | 不能 | **能**(誤差歸因報告) |
| 新台校正失敗時能不能 fallback 到完整流程 | N/A | 能(L4 = 現行流程) |

---

## 3. 設計範疇與假設

### 3.1 鎖定的「同系列」等級

本設計鎖定 **等級 2:同型號**。定義如下:

| 維度 | 同型號的要求 |
|---|---|
| 光路設計 | 完全相同(NA、放大倍率、波長、像素尺寸、軸向間距等) |
| 物鏡規格 | 相同型號(可能不同生產批次) |
| 光源類型 | 相同(LED 型號、驅動條件相同) |
| 相機 | 相同 sensor 型號、相同 ROI 設定 |
| 個體公差 | **允許存在**(這正是要校正的對象) |

### 3.2 不在本設計範疇內的場景

| 場景 | 為什麼不處理 | 對應的處理方式 |
|---|---|---|
| 跨型號(不同光路設計) | 機型先驗失效,從零跑反而更安全 | 直接走 L4 = 現行流程 |
| 同設計但不同元件批次(等級 3) | 機型 std 會被低估,容易 false acceptance | 本設計提供 fallback,但不保證精度 |
| 同一台機的拆裝重校(原問題情境的 subset) | 是「同型號」的特例(同一台 = 同型號的 N=1 子集) | 本設計**自然涵蓋**,但效能會更好(因為先驗更強) |

### 3.3 核心假設(必須驗證,若失效則本設計無效)

| 編號 | 假設 | 驗證方式 | 失效時的處理 |
|---|---|---|---|
| H1 | 同型號機台之間的 PSF 差異**主要集中在低階 Zernike 模態**(Z2/Z3 tilt, Z4 defocus, Z5/Z6 astig) | 累積 ≥ 3 台同型號機台後,看 Δ Zernike 的模態分佈 | 設計失效,需重新設計階梯 L3 的「可解釋模態」清單 |
| H2 | 同型號機台之間的差異**幅度可被視為高斯分佈或近似如此** | 累積 ≥ 5 台後,做 normality test | 失效則改用 robust statistics(median ± MAD),不用 mean ± std |
| H3 | 機型模板的 reference 點(中位數)**對絕大多數新機都是 BADS 收斂域內的好起點** | A 階段 L3 實驗 — 拆裝後仍能熱啟動收斂 | 失效則需要更複雜的「多模態 prior」 |
| H4 | 不同 FOV 點的 PSF 變化**是空間平滑的** | 視覺檢查 fitted_psf_grid.png 跨 FOV 的形狀變化 | 失效則 L1 的 9 點稀疏取樣不足以代表全 FOV |

**注意**:H1–H4 在本設計上線前都沒有完整證據。A 階段實驗(§10)就是為了驗證這些假設。

---

## 4. 核心想法(整體哲學)

### 4.1 一句話

**從零開始 → 從機型 reference 開始;固定流程 → 階梯式根據漂移大小決定要爬到哪一級。**

### 4.2 用對日常生活的比喻

整個新方法像是「**考試對答案 + 改題目**」的模式:

| 現行流程 | 新方法 |
|---|---|
| 每次考試都從沒讀過書開始唸 | 已經有「機型考古題模板」,只要針對這次考卷的差異微調 |
| 不管考得好不好,都唸同樣多時間 | 先估這次考多差,差越多才唸越久 |
| 考完不知道為什麼考差 | 考完有一份「為什麼這次跟標準有差」的歸因報告 |

### 4.3 兩個解耦的決策

新方法有兩個獨立但互相支援的設計決策:

#### 決策 A:**用機型先驗,而不是預設 x0**
- 機型 reference 提供「起點」與「合理搜尋範圍」
- 對同型號場景,這個先驗是強到能跳過絕大多數 BADS 探索成本的

#### 決策 B:**階梯式校正,而不是固定流程**
- 從最便宜的「不擬合,只 sanity check」開始試
- 每一級有量化的「升級條件」決定要不要爬到下一級
- 99% 的同型號機台應該停在 L1 或 L2,不需要跑到 L4

**這兩個決策可以分開實作**(先做 A,後做 B,或反之),但合在一起才有最大效益。

### 4.4 跟「拆裝重校」場景的關係

雖然本設計的主場景是「同型號跨機」,但「同一台拆裝重校」其實是它的特例:

| 場景 | 用什麼當機型模板 |
|---|---|
| 同型號跨機 | 該機型的累積平均 PSF |
| 同一台拆裝後重校 | **這台拆裝前自己的 PSF**(N=1 的「機型」) |

所以同一份程式碼就能涵蓋兩個場景,只是換掉「模板從哪來」。

---

## 5. 系統架構總覽

### 5.1 兩個核心 Artifact

新方法由兩個獨立 artifact 構成:

```
┌─────────────────────────────────┐      ┌─────────────────────────────────┐
│  A. 機型模板                     │      │  B. 快速校正流程                 │
│     (Machine-Type Template)     │ ───▶│     (Quick Recalibration)       │
│                                 │      │                                 │
│  - 中位數 Zernike 係數           │      │  - L0–L4 階梯式擬合              │
│  - 各係數的合理變動範圍 (std)    │      │  - 每一級用模板當起點 / 範圍     │
│  - 該機型的擬合品質基準           │      │  - 自動升級到下一級              │
│  - 治理 metadata                │      │  - 輸出該台 PSF + 歸因報告        │
│                                 │      │                                 │
│  生成頻率:每個機型一次           │      │  生成頻率:每台新機一次          │
│  (之後累積機台時更新)            │      │                                 │
└─────────────────────────────────┘      └─────────────────────────────────┘
```

### 5.2 整體流程圖

```
                       ┌────────────────────────────────────┐
                       │  種子機(R26NewPSF)的完整擬合      │
                       │  (現有資產,已存在)                │
                       │  → PSF_fitted_2D_FOVstack.mat     │
                       └────────────────┬───────────────────┘
                                        │ (一次性)
                                        ▼
                       ┌────────────────────────────────────┐
                       │  建立機型模板 v1(種子階段)        │
                       │  → reference_template.mat         │
                       └────────────────┬───────────────────┘
                                        │
                                        ▼
                       ┌────────────────────────────────────┐
                       │  A 階段驗證實驗(L0–L3 拆裝)       │
                       │  → 校準階梯閾值 + 量化 noise floor │
                       └────────────────┬───────────────────┘
                                        │ (一次性,本設計通過驗收)
                                        ▼
                       ┌────────────────────────────────────┐
                       │  快速校正流程上線                   │
                       └────────────────┬───────────────────┘
                                        │
                                        ▼
                       ┌────────────────────────────────────┐
                       │  每台新機:跑 L0 → L1 → L2 → ...   │
                       │  → 該台 PSF + 歸因報告              │
                       └────────────────┬───────────────────┘
                                        │ (每台機)
                                        ▼
                       ┌────────────────────────────────────┐
                       │  自動更新機型模板(增加 source)    │
                       │  → 模板從種子階段 → 早期 → 成熟    │
                       └────────────────────────────────────┘
```

### 5.3 為什麼是兩個獨立 Artifact 而不是合一

| 設計選擇 | 優點 | 缺點 |
|---|---|---|
| **分開**(本設計) | 模板可獨立更新、版本管理乾淨、可被其他工具讀(例如 PSF_Report_Helper) | 需要設計 schema 與治理 |
| 合一(模板嵌在程式裡) | 程式自包含 | 模板更新就要 git commit,治理成本高 |

選分開的理由:**機型模板會隨著機台累積而頻繁更新,但流程程式應該穩定**。耦合在一起會違反「資料 vs 程式」的分離原則。

---

## 6. 機型模板的詳細規格

### 6.1 概念:模板不是一張 PSF,而是「PSF 的分佈描述」

很多人會直覺地以為「機型模板 = 一張平均 PSF」,但這是不夠的。原因:
- 平均 PSF 只能當「起點」,**不能告訴你新機是不是 outlier**
- 平均 PSF 沒有「合理變動範圍」,**搜尋範圍只能憑直覺設**
- 平均 PSF 沒有「品質基準」,**新機擬合好不好沒有比較對象**

所以機型模板必須存「分佈」級別的資訊,不只是平均值。

### 6.2 模板的內容(schema)

機型模板存成 MATLAB `.mat` 結構 `machine_type_template`,內容如下:

```matlab
machine_type_template = struct();

% --- 識別與治理 ---
machine_type_template.model_id          = 'GMM_v1_NA023_M20x';     % 機型唯一識別
machine_type_template.template_version  = 'v1.0.0';                % 模板版本(語意化)
machine_type_template.maturity_stage    = 'seed' | 'early' | 'mature';  % §8 詳述
machine_type_template.created_date      = '2026-04-18';
machine_type_template.last_updated      = '2026-04-18';
machine_type_template.contributor_count = 1;                       % 貢獻機台數

% --- 核心數值內容(per-FOV) ---
% 形狀 [n_zernike=15, grid_rows=10, grid_cols=10]
machine_type_template.coef_median       = double(15, 10, 10);      % 各 FOV 的中位數 Zernike 係數
machine_type_template.coef_std          = double(15, 10, 10);      % 各 FOV 的係數 std(內容由 std_source 決定)
machine_type_template.coef_mad          = double(15, 10, 10);      % robust 替代:median absolute deviation(early/mature 階段才有意義)
machine_type_template.std_source        = 'proxy_repeat_fit' | 'sample_across_machines';
                                                                    % 'proxy_repeat_fit'   = 種子階段,coef_std 來自同機多次擬合(§8.3.1)
                                                                    % 'sample_across_machines' = early/mature 階段,coef_std 來自跨機 sample std

% --- PSF 物件(per-FOV)---
% 形狀 [psf_h=101, psf_w=101, grid_rows=10, grid_cols=10]
machine_type_template.psf_median        = double(101, 101, 10, 10); % 平均 PSF(用 coef_median 重建)

% --- 品質基準 ---
machine_type_template.fval_median       = double(10, 10);           % 各 FOV 中位數擬合誤差
machine_type_template.fval_p95          = double(10, 10);           % 95-percentile 擬合誤差(品質上界)

% --- 模板來源治理 ---
machine_type_template.source_machines = struct( ...
    'machine_id',     {{'machine_001', 'machine_002', ...}}, ...
    'fitted_psf_path', {{'.../source_machines/machine_001.mat', ...}}, ...
    'fit_date',       {{'2026-03-26', '2026-04-15', ...}}, ...
    'operator',       {{'Rio', 'Rio', ...}}, ...
    'notes',          {{'種子機,R26NewPSF formal fit', ...}} ...
);
```

### 6.3 為什麼存「中位數 + std」而不是「平均 + std」

選擇 **中位數 (median) + MAD** 作為主要統計量,而 mean + std 作為次要參考。理由:

| 統計量 | 對 outlier 的敏感度 | 對小樣本的穩定性 |
|---|---|---|
| Mean + std | 敏感(一台壞機會拉走整個模板) | 不穩 |
| **Median + MAD** | 不敏感(50% breakdown point) | 較穩 |

由於模板早期可能只有 3–5 台機,**任何一台壞機都會嚴重污染統計量**,所以默認用 robust statistics。

### 6.4 PSF 物件 vs 係數,為什麼要存兩份

| 存什麼 | 用在哪裡 |
|---|---|
| `coef_median` | 給 BADS 當起點(BADS 吃 15 維向量) |
| `psf_median` | 給 L0 sanity check 直接做反捲積(不用每次重算 PSF) |

這是一個 cache 設計:`psf_median` 可以從 `coef_median` 用 `aberration()` 重新生成,但每次計算太慢。模板存好可以直接用。

### 6.5 命名規則與檔案位置

```
PSF_Fitting/machine_type_templates/
└── <model_id>/
    ├── reference_template.mat           # 主模板檔
    ├── reference_template.json          # 模板 metadata 的 JSON 鏡像(便於 Python 讀取)
    ├── source_machines/                 # 每台貢獻機台的 fitted PSF 副本
    │   ├── machine_001_seed.mat
    │   ├── machine_002.mat
    │   └── ...
    ├── visualizations/                  # 模板的視覺化(median PSF heatmap、std heatmap)
    │   ├── median_psf_grid.png
    │   ├── std_per_coefficient.png
    │   └── coverage_per_fov.png
    └── MANIFEST.md                      # 治理紀錄(中文)
```

`MANIFEST.md` 內容:
- 模板的歷史(每次更新的日期、原因、貢獻機台、版本號)
- 已知限制(例如「此模板只覆蓋 NA=0.23 機型」)
- 已知 outlier(被排除的機台與排除原因)

### 6.6 模板的版本管理

採用 **語意化版本號**:`vMAJOR.MINOR.PATCH`

| 版本變動 | 觸發條件 |
|---|---|
| **MAJOR** | schema 不相容變更(例如新增/刪除欄位)、機型重新定義 |
| **MINOR** | 新增 source machine、coverage 升級到下一個 maturity stage |
| **PATCH** | 修正單台機的 metadata、補上遺漏資料 |

**舊版本不能被刪除**,要保留在 `machine_type_templates/<model_id>/archive/` 下,因為早期校過的機台可能要用當時的模板回溯歸因。

---

## 7. 快速校正階梯的詳細規格

### 7.1 階梯總表

| 級 | 名稱 | 在做什麼 | 起點 | 搜尋範圍 | 預估時間 | 升級條件 |
|---|---|---|---|---|---|---|
| **L0** | Sanity check | 不擬合,直接套模板做反捲積 | 模板 `coef_median` | — | < 1 分 | 反捲積 RMSE > 模板 fval_p95 × 2 |
| **L1** | 稀疏抽樣熱擬合 | 9 個 FOV 點熱擬合 | 模板 `coef_median` | ±2σ(per-coef) | 1–3 分 | 任一 FOV 偏離模板 > 3σ;或 9 點 RMSE > 基準 × 1.5 |
| **L2** | 全 FOV 窄搜尋 | 100 點熱擬合 + 窄搜尋 | 模板 `coef_median` | ±2σ(per-coef) | 10–15 分 | 全 FOV 殘差 > 模板 fval_p95 × 1.5 |
| **L3** | 模態降維重擬合 | 100 點,只動 4–6 個可解釋模態 | L2 結果 | ±4σ(僅 Z2-Z6) | 20–30 分 | 殘差仍壓不到模板 fval_p95 × 1.2 |
| **L4** | 兜底:現行完整流程 | 100 點 + 預設 x0 + 寬搜尋 | 預設 `[0,...,0,1]` | 無限制 | 1.5–2 hr | (不再升級,L4 是終點) |

### 7.2 L0 — Sanity Check(不擬合)

**目的**:用最低成本確認「機型模板對這台新機有沒有用」。

**輸入**:
- 機型模板的 `psf_median`
- 該新機的 100 張 FOV 影像(已頻率濾波)
- GT 影像

**處理**:
- 對每張新機 FOV 影像,用模板 `psf_median` 做 forward simulation,計算 simulated vs measured 的 RMSE
- 統計 100 張的 RMSE 分佈

**升級條件(白話)**:
- 如果 100 張的 RMSE 都跟模板 fval 接近 → **L0 通過**,直接用模板當這台 PSF
- 如果有任何一張的 RMSE 顯著偏大 → 升級 L1

**量化升級條件**:
```
升級 L1 if  median(RMSE_per_fov) > template.fval_median * 2
         OR p95(RMSE_per_fov)    > template.fval_p95 * 2
         OR any(RMSE_per_fov)    > template.fval_p95 * 5
```

**估計時間**:< 1 分鐘(純 forward sim,無 BADS)

### 7.3 L1 — 稀疏抽樣熱擬合

**目的**:用最少擬合次數判斷這台機是否在合理變動範圍內。

#### 7.3.1 為什麼是 9 個 FOV 點

選 9 個點(對應 10×10 grid 的 [1,1], [1,5], [1,10], [5,1], [5,5], [5,10], [10,1], [10,5], [10,10])。理由:
- **空間覆蓋**:角落 + 中心 + 邊中,捕捉 FOV 內的空間變化主軸
- **計算成本**:從 100 → 9 是 ~11x 加速
- **統計足夠**:9 個點足以判斷係數差是「集中性偏移」還是「隨機散布」

**替代方案考慮**:
- 5 點(corners + center):太少,空間覆蓋不夠
- 25 點(5×5 二次 grid):成本接近 1/4 全部,效益不顯著
- 隨機抽樣:無法跨機台直接比對(每次抽不同點)

#### 7.3.2 熱擬合的具體設定

對每個 FOV 點 (i, j):
- **起點 x0**:`template.coef_median(:, i, j)`
- **搜尋範圍**:`x0 ± 2 * template.coef_std(:, i, j)`(seed 階段用代理 std,§8)
- **BADS options**:tolerance 收緊(例如 `OptimalityTolerance=1e-4` 比現行的 1e-5 鬆)
- **MaxFunEvals**:減半(例如從 400 → 200)

#### 7.3.3 升級條件

```
判斷 1:係數一致性
  for each (i, j) in 9 points:
    delta_coef = fitted_coef(:, i, j) - template.coef_median(:, i, j)
    z_score    = delta_coef ./ template.coef_std(:, i, j)
  if any |z_score| > 3:
    升級 L2(這個 FOV 偏太多,9 點不足以代表)

判斷 2:殘差一致性
  if median(fval_9pts) > template.fval_median * 1.5:
    升級 L2(整體擬合品質劣於模板基準)
```

**通過 L1**:
- 對未擬合的 91 個 FOV 點,用 9 點 + 模板做空間插值(例如 thin-plate spline)生成 PSF
- 輸出最終 100-FOV PSF

**估計時間**:9 張 BADS × ~10 秒/張 = 1.5 分鐘 + 插值 < 1 分鐘 ≈ **1–3 分鐘**

### 7.4 L2 — 全 FOV 窄搜尋

**目的**:當 9 點不足以代表時,跑完整 100 張,但用模板限制搜尋範圍。

#### 7.4.1 與現行流程的差異

| 項目 | 現行(L4) | L2 |
|---|---|---|
| 起點 x0 | `[0,...,0,1]` | `template.coef_median(:, i, j)`(每張不同) |
| 搜尋範圍 | 無限制 | `x0 ± 2 * template.coef_std(:, i, j)` |
| Warm start | 用前一張 | **不需要**(模板 prior 已經夠強) |
| MaxFunEvals | ~400 | ~150–200 |

#### 7.4.2 為什麼比現行流程快很多

- **起點更接近真解** → BADS 探索 phase 縮短
- **搜尋範圍縮小** → mesh 點數少
- **不需要 warm-start 的依賴鏈** → 100 張可平行(若 GPU 記憶體允許)

預估加速比 **3–6x**(取決於模板成熟度)。

#### 7.4.3 升級條件

```
if median(fval_100) > template.fval_median * 1.5:
  升級 L3(模板雖然能限制搜尋,但這台跟模板差太多,需要放寬)

if any(fval_per_fov) > template.fval_p95 * 3:
  flag 該 FOV 為「異常點」,但若其他 FOV 都 OK,仍可通過 L2
```

**通過 L2**:輸出 100-FOV PSF,精度應接近 L4。

**估計時間**:100 張 × 6–10 秒/張(縮短後)= **10–15 分鐘**

### 7.5 L3 — 模態降維重擬合

**目的**:當這台機跟模板差較多,但還在合理範圍時,放寬搜尋但只動「物理上會變的模態」。

#### 7.5.1 哪些是「可解釋模態」

根據假設 H1(§3.3):

| Zernike 模態 | 編號 | 物理意義 | 重組後是否常變 |
|---|---|---|---|
| Y-tilt | Z2 | 整機/相機傾斜 | 常變(但 WholeFOV 強制鎖 0) |
| X-tilt | Z3 | 同上 | 同上 |
| Defocus | Z4 | 對焦/working distance | **非常常變** |
| Astig 0° | Z5 | 物鏡安裝公差 | 常變 |
| Astig 45° | Z6 | 同上 | 常變 |
| Coma 低階 | Z7, Z8 | 光路偏心 | 偶爾變 |

L3 只擬合 **Z4, Z5, Z6**(3 個);若 Z2/Z3 後來決定不鎖 0,則加入,共 5 個。

#### 7.5.2 處理

對每個 FOV 點:
- **起點**:L2 的擬合結果(若 L2 沒跑,則用模板 `coef_median`)
- **可變維度**:只 Z4, Z5, Z6(其他 11 個固定為起點值)
- **搜尋範圍**:`±4σ`(放寬,但只放這 3 維)
- **MaxFunEvals**:ample(因為維度低,收斂快)

#### 7.5.3 為什麼這樣設計

降維後:
- BADS 在 3 維搜尋遠快於 15 維
- 物理上也合理(同型機台高階像差應該幾乎相同)
- 過擬合風險大幅降低

#### 7.5.4 升級條件

```
if median(fval_100) > template.fval_median * 1.2:
  升級 L4(這台已經偏離同型號定義,需完整流程兜底)
```

**估計時間**:100 張 × 12–18 秒/張(維度低但搜尋寬)= **20–30 分鐘**

### 7.6 L4 — 完整流程兜底

**目的**:當前面所有級都無法收斂時的安全網。等價於現行 `HDR_fitting_2D_WholeFOV.m`。

**進入 L4 的意涵**:這台機可能:
- 不是同型號(可能 mislabeled)
- 元件批次差異大(超出本設計範疇)
- 安裝/對齊嚴重異常(需人工檢查)

**L4 完成後**:
- 輸出 PSF 仍進入 §6.5 的 `source_machines/`,但**標記為 "outlier_candidate"**
- 治理上需要人工 review,決定是否納入模板更新

### 7.7 階梯流程的 pseudocode

```
function quick_recalibration(new_machine_images, gt, template):
    # L0
    L0_result = sanity_check(new_machine_images, template)
    if L0_passes(L0_result, template):
        return template.psf_median, "L0", L0_result

    # L1
    L1_result = sparse_warm_fit(new_machine_images, gt, template, n_points=9)
    if L1_passes(L1_result, template):
        psf = interpolate_full_fov(L1_result, template)
        return psf, "L1", L1_result

    # L2
    L2_result = full_warm_narrow_fit(new_machine_images, gt, template)
    if L2_passes(L2_result, template):
        return L2_result.psf, "L2", L2_result

    # L3
    L3_result = modal_only_fit(new_machine_images, gt, template, modes=[4,5,6])
    if L3_passes(L3_result, template):
        return L3_result.psf, "L3", L3_result

    # L4 fallback
    L4_result = current_full_pipeline(new_machine_images, gt)
    flag_as_outlier_candidate(L4_result)
    return L4_result.psf, "L4", L4_result
```

---

## 8. 機型模板的三個成熟階段

### 8.1 為什麼需要分階段

機型模板的 std(`coef_std`)需要 **多台機台的樣本** 才能算出來。但實務上:
- 第一台只有種子機,沒有 std 可言
- 早期幾台時 std 不穩,會誤判
- 累積到一定數量後 std 才穩定

所以模板有 **三個成熟階段**,每個階段對應不同的使用方式與升級條件。

### 8.2 三階段定義

| 階段 | 貢獻機台數 | std 來源 | 階梯可用級別 | 風險 |
|---|---|---|---|---|
| **種子(seed)** | 1 | **代理 std**:用該機台 BADS 重複擬合 5 次的內部 std | L0, L1, L2(L3 不建議) | 高 false positive(代理 std 通常偏小) |
| **早期(early)** | 2–4 | 用該幾台的 sample std(雖然樣本少) | L0–L3 都可用 | 中 false positive |
| **成熟(mature)** | ≥ 5 | 真實 sample std + MAD | L0–L4 全可用 | 低 |

### 8.3 種子階段的詳細處理

#### 8.3.1 代理 std 的計算

由於只有 1 台機,沒辦法直接算「跨機 std」。改用 **「同一台機,多次擬合的 std」** 作為代理:

```
for each FOV (i, j):
    for trial in 1..5:
        result_trial = BADS_fit(seed_machine_image[i,j], gt, x0=random)
    coef_proxy_std(:, i, j) = std(result_trial.coef across trials)
```

**為什麼這個代理是低估**:
- 真實「跨機 std」 = 個體公差 + 安裝公差 + 拍攝噪聲 + 擬合噪聲
- 「同台多擬合 std」 = 只有「擬合噪聲」一項
- 所以代理 std **嚴重低估真實 std**

#### 8.3.2 為了補償低估,做兩件事

1. **搜尋範圍放大**:L1/L2 的搜尋範圍從 ±2σ → **±4σ**(用代理 σ 時)
2. **升級閾值放鬆**:z-score 升級門檻從 3 → **5**(用代理 σ 時)

#### 8.3.3 種子階段的特殊治理規則

- 第一台「真正的新機」(不是種子機本身)跑完後,要 **人工 review** 結果
- 確認結果合理後,才升級模板到「早期階段」

### 8.4 早期階段的特殊風險

**主要風險:小樣本 std 的不穩定性**。

例如 N=3 時:
- 若 3 台中有 1 台是 outlier,sample std 會被拉大 → 搜尋範圍過寬 → 沒 catch 到問題
- 若 3 台都剛好集中,sample std 被低估 → 搜尋範圍過窄 → false positive

**緩解策略**:
- 用 MAD 而不是 std(對 outlier 不敏感)
- 額外保留「最大觀測差異 × 1.5」作為搜尋範圍的下界(防止 std 過度低估)
- 任何新機若被 L4 兜底,必須人工 review,**不自動納入模板**

### 8.5 階段升級的觸發條件

| 從 → 到 | 條件 |
|---|---|
| seed → early | 第 2 台機完成校正且通過 review |
| early → mature | 第 5 台機完成且 sample std 通過穩定性檢查(例如 leave-one-out 重算 std 後變動 < 20%) |
| mature → ??? | 不再升級,但模板版本繼續迭代 |

---

## 9. 誤差歸因方法

### 9.1 為什麼需要歸因

當新機跑完快速校正後,結果跟模板 reference **總是會有差異**。問題是:
- 這個差異是「擬合演算法本身的隨機抖動」?(無實質意義)
- 還是「拍攝/影像本身的雜訊」?(可改善硬體)
- 還是「機台真的跟同型號平均不同」?(校正完成,結束)

如果不能區分這三者,就會誤判機台狀態(例如把擬合抖動當成機台問題,白白拉長校正時間)。

### 9.2 三層歸因測試

把差異拆成三個來源,**用三個獨立測試各自排除**:

```
新機差異 (Δ)
     │
     ▼
Test 1: 是否大於擬合 noise floor?
     │
   yes ─▶ Test 2: 差異有空間結構嗎?
                   │
                 yes ─▶ Test 3: 集中在物理可解釋模態嗎?
                                 │
                               yes ─▶ 機台真實變化(可解釋)✓
                                no ─▶ 警訊:可能擬合過擬合 ⚠
                  no ─▶ 擬合不穩,加正則化或重跑 ⚠
   no ─▶ 沒實質變化,擬合雜訊而已 ✓
```

### 9.3 Test 1 — 擬合 noise floor 測試

**問題**:差異 Δ 是不是只是 BADS 本身的收斂隨機性?

**做法**:
- 從 A 階段 L0 實驗(§10.2)得到「同一張影像,BADS 跑 N 次」的係數 std,稱為 `noise_floor_std`
- 計算 z-score:`z = |Δ_per_coef| / noise_floor_std`

**判決**:
```
if median(|z|) < 2:  # 95% 在 noise floor 內
    判決 = "no_real_change"
    停止後續測試
else:
    繼續 Test 2
```

**為什麼是 z<2 而不是 z<3**:用 95% CI 而非 99.7%,在「不確定是否要升級」時偏向保守(寧可 false positive 升級到 L2 也不要 missed detection)。

### 9.4 Test 2 — 空間結構測試

**問題**:Δ 在 100 個 FOV 上是「全部朝同一方向偏」(機台變了)、還是「東一塊正西一塊負」(擬合雜訊)?

**做法 A:全 FOV 同號比例**:
```
for each Zernike coef k:
    pos_ratio = count(Δ_k(i,j) > 0) / 100
    if pos_ratio > 0.7 OR pos_ratio < 0.3:
        該係數有空間結構(系統性偏移)
```

**做法 B:Moran's I(空間自相關)**:
- 計算 Δ 的 Moran's I,> 0 代表空間平滑(系統性);≈ 0 代表隨機
- 比 A 更嚴謹但計算成本稍高

**判決**:
```
structured_coefs = which coefficients show spatial structure
if len(structured_coefs) == 0:
    判決 = "fitting_noise_artifact"
    建議 = "增加 BADS iterations 或加正則化"
else:
    繼續 Test 3
```

### 9.5 Test 3 — 模態定位測試

**問題**:有空間結構的係數,集中在「物理上會變的模態」嗎?

**判決邏輯**:
```
explanable_modes = {Z4_defocus, Z5_astig, Z6_astig, Z2_tilt, Z3_tilt}
if structured_coefs ⊆ explanable_modes:
    判決 = "real_machine_change_explainable"
    輸出 = "機台變了,變化集中在 [模態]"
elif structured_coefs ∩ explanable_modes 非空 AND 也包含高階模態:
    判決 = "real_change_with_high_order_warning"
    輸出 = "機台變了,但有高階模態異常,建議人工查"
else:  # 全部集中在不該變的高階模態
    判決 = "suspicious_overfit"
    輸出 = "警訊:差異集中在不該變的模態,可能擬合過擬合"
```

### 9.6 三測試的綜合判決表

| Test 1 | Test 2 | Test 3 | 綜合判決 | 建議行動 |
|---|---|---|---|---|
| z < 2 | — | — | no_real_change | 直接收下校正結果 |
| z ≥ 2 | 無結構 | — | fitting_noise_artifact | 增加 iterations 或加正則化 |
| z ≥ 2 | 有結構 | 集中可解釋模態 | real_machine_change_explainable | 收下,記錄變化模態 |
| z ≥ 2 | 有結構 | 部分高階 | real_change_with_high_order_warning | 收下但 flag,人工查 |
| z ≥ 2 | 有結構 | 集中不可解釋 | suspicious_overfit | **不收**,降級到 L2 重跑 |

### 9.7 歸因報告的輸出格式

每台機跑完後,生成 `.../<machine_id>/attribution_report.md`:

```markdown
# 機台 machine_007 校正歸因報告

- 校正日期:2026-04-20
- 階梯停在:L2
- 與機型模板的偏離程度:中

## Test 1:擬合 noise floor 測試
- median |z|:3.5(> 2,**判決:有實質差異**)
- 各係數 z-score 分佈:[圖]

## Test 2:空間結構測試
- 有結構的係數:Z4 (defocus), Z6 (astig 45°)
- Moran's I:Z4=0.81, Z6=0.62
- [10x10 Δ 熱圖]

## Test 3:模態定位
- 有結構模態:{Z4, Z6}
- 全部 ⊆ 可解釋模態
- **判決:real_machine_change_explainable**

## 結論
- 此台機台跟同型號平均的主要差異是:**defocus 偏 +0.18, astig 45° 偏 -0.12**
- 物理解釋:可能對焦距離略短於標準 + 物鏡公差造成輕微像散
- 建議行動:**校正完成,可上線**
```

---

## 10. 算法驗證實驗(A 階段)

### 10.1 為什麼必須做 A 階段驗證

新方法的所有閾值(z-score 門檻、升級條件、噪聲基線)都是**設計階段假設的**。
沒有實驗證據前,這些閾值可能:
- 太嚴 → 全部升級 L4,新方法無加速效果
- 太鬆 → 大量 false acceptance,校正品質下降

A 階段實驗的目的是 **校準閾值** + **驗證假設 H1–H4**(§3.3)。

### 10.2 四層實驗設計

| 層 | 動作 | 重複次數 | 回答的問題 | 對應的判決 |
|---|---|---|---|---|
| **L0** | 同一張影像,BADS 跑 N 次 | 5 | BADS 本身的隨機性 | Test 1 的 noise floor |
| **L1** | 同機台,重新拍 100 張 | 3 | 拍攝噪聲 + 擬合噪聲 | Test 1 的擴大 noise floor |
| **L2** | 假介入(關機重開、輕碰機台,不拆) | 2 | 偽陽性率(false alarm) | 階梯不該被誤判升級 |
| **L3** | 真介入(拆裝物鏡) | 3–5 | 真陽性率 + 模態歸因正確性 | 階梯應正確識別 |

### 10.3 實驗的時程估計

**一天可完成版本(MVE)**:

| 時段 | 動作 |
|---|---|
| 09:00–10:00 | 開機暖機(光機溫度穩定 30–60 分) |
| 10:00–10:30 | L0 資料來源:拍第一組 100 張 |
| 10:30–12:00 | L1 重拍 ×3 次(每次 30 分) |
| 12:00–13:00 | 午休(順便讓機台溫度漂回) |
| 13:00–14:30 | L2 假介入 ×2 次(每次 45 分,含介入動作) |
| 14:30–17:30 | L3 拆裝 ×3 次(每次 1 小時,含拆裝 + 重拍) |
| 17:30 | 收工,擬合掛機跑一夜(L0 跑 5 次 + 其他各 1 次) |

### 10.4 必須記錄的 metadata

| 項目 | 為什麼 |
|---|---|
| 每次拍攝的時間 + 室溫 | thermal drift 是常被忽略的污染 |
| 拆裝動作的描述(只擰下鏡筒?整個鏡頭組?) | 變數隔離 |
| 拆裝者(若多人) | 操作差異 |
| GT 樣本是否被動過(理應否) | 位置變數隔離 |
| 物鏡是否被擦/清(理應否) | 元件變數隔離 |

### 10.5 實驗的污染控制清單

**禁止項目**:

| 不要做 | 為什麼會污染 |
|---|---|
| 拆裝中順便清鏡頭 | 變兩個變數 |
| 換不同物鏡 | 同上,且更大變數 |
| 中間移動 GT 樣本 | 影像位置變,Zernike 中心被吃掉 |
| 一天做不完拖到隔天 | 室溫 5°C 差足以造成可量測的 PSF 漂移 |
| L3 拆裝交給不同人 | 操作差異混入 |

### 10.6 拿到資料後怎麼用

#### 10.6.1 校準 Test 1 的 noise floor

從 L0(5 次同影像擬合)算每個 FOV 點、每個 Zernike 係數的 std,
這就是 `noise_floor_std`,用於後續所有 Test 1 計算。

#### 10.6.2 校準階梯升級閾值

對 L1, L2, L3 的每組資料,**平行跑兩條路線**:
- 路線 A:現行 L4 完整流程(當作 ground truth PSF)
- 路線 B:新階梯流程(看停在哪一級,輸出對應 PSF)

對比指標:
- 階梯停在哪一級的分佈
- 停下時 PSF 跟 L4 ground truth 的差異(MSE、Zernike 範數)
- 反捲積結果跟 SEM GT 的對比(下游影響)
- 實際時間節省

#### 10.6.3 驗證歸因方法的準確率

對 L1, L2, L3 各組,跑三層歸因測試,看是否得到正確判決:

| 實驗組 | 期望判決 |
|---|---|
| L1 (拍攝重複) | "no_real_change" 或 "fitting_noise_artifact" |
| L2 (假介入) | "no_real_change" |
| L3 (真拆裝) | "real_machine_change_explainable",且模態集中在 Z4/Z5/Z6 |

計算混淆矩陣 + ROC,得到:
- 真陽性率(TPR):L3 中有多少被正確識別為「機台變了」
- 偽陽性率(FPR):L1+L2 中有多少被誤判為「機台變了」
- 模態歸因正確率:L3 中模態判定是否落在預期清單

### 10.7 A 階段的 acceptance criteria

新方法上線前,A 階段實驗結果必須滿足:

| 指標 | 最低要求 |
|---|---|
| L1+L2 的 false positive rate | < 10% |
| L3 的 true positive rate | > 80% |
| L3 的模態歸因正確率(模態集中在 Z4/Z5/Z6) | > 70% |
| L2 階梯結果與 L4 的 PSF MSE | < L4 自身重複的 MSE × 2 |
| L1 的時間節省 | > 5x |
| L2 的時間節省 | > 3x |

**任一未達標 → 設計需修正,回到 §6 / §7 重新調整。**

---

## 11. 與現有系統的整合

### 11.1 與 `HDR_fitting_2D_WholeFOV.m` 的關係

**新方法不取代現行流程,而是在它之上加一層**。

```
新機進來
     │
     ▼
┌──────────────────────────────┐
│  quick_recalibration/         │
│  L0 → L1 → L2 → L3            │
└──────────┬───────────────────┘
           │ (若 L3 失敗)
           ▼
┌──────────────────────────────┐
│  L4 = HDR_fitting_2D_WholeFOV │ ← 不變,保持兜底
└──────────────────────────────┘
```

**現行流程的變動量:零**。`HDR_fitting_2D_WholeFOV.m` 與 `_impl.m` 不修改,只是被 L4 wrapper 呼叫。

### 11.2 與 `PSF_Fitting_ValidationLab/` 的關係

ValidationLab 是現有的「Whole-FOV 修正驗證沙盒」,負責現行流程的歷史比較。

**新方法的實驗(§10)應放在哪裡?**
- A 階段實驗紀錄與 raw 資料 → `quick_recalibration/validation_experiments/`(獨立於 ValidationLab)
- 因為 A 階段是**新方法**的驗證,不是現行流程的驗證,放 ValidationLab 會混淆

但兩者**共用基礎設施**:
- 相同的 BADS 呼叫慣例
- 相同的 fitted_psf 視覺化工具(`visualize_fitted_psf_grid.m`)

### 11.3 與 `PSF_Report_Helper/` 的關係

`PSF_Report_Helper` 目前負責把現行 Whole-FOV 結果變成繁中報告。

**新方法擴充 Report Helper**:
- 新增 `recalibration_report.py`:吃單台機的快速校正結果 + 歸因報告,輸出繁中校正紀錄
- 新增 `template_summary.py`:吃機型模板,輸出模板現況的繁中描述(包含成熟度、貢獻機台清單)

### 11.4 與下游 `Model/` 的綁定

現行綁定:
- `Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py` 直接讀
  `Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`

新方法後的綁定提案:
- 每台機的 PSF 輸出到 `quick_recalibration/per_machine_results/<machine_id>/PSF_fitted_2D_FOVstack.mat`
- 訓練腳本可以指定要讀哪一台機的 PSF,或讀機型模板的 `psf_median`
- 預設仍指向現行路徑,**確保 backward compatibility**

### 11.5 與 PSF 政策的關係

根據 [`docs/policy/PSF_POLICY_TRANSITION_R26.md`](../../docs/policy/PSF_POLICY_TRANSITION_R26.md),
目前正式 PSF 標準是「新 Whole-FOV PSF(2026-03-26 完成)」。

**新方法的 PSF 政策定位**:
- 機型模板的種子機 = R26NewPSF 那台,即現行正式標準
- 機型模板本身應視為「正式標準的衍生物」,享有同等地位
- 各台機的 PSF 視為「該台的個體標準」,**不取代機型模板**(模板是同型號的中位描述)

### 11.6 與 `PROJECT_STATE.md` 的關係

新方法穩定後,`PROJECT_STATE.md` 應新增一節:
```markdown
## 8. PSF Quick Recalibration / PSF 快速校正流程
- 同型號機台快速校正流程,以機型模板為先驗
- 主文件:PSF_Fitting/quick_recalibration/DESIGN_TW.md
- 機型模板位置:PSF_Fitting/machine_type_templates/<model_id>/
- 階梯流程入口:PSF_Fitting/quick_recalibration/run_quick_recalibration.m
```

---

## 12. 建議的檔案結構

### 12.1 完整目錄樹

```
PSF_Fitting/
├── quick_recalibration/                         ← 本設計新增
│   ├── DESIGN_TW.md                            ← 本文件
│   ├── README_TW.md                             ← 給操作者的快速使用指南
│   ├── run_quick_recalibration.m                ← MATLAB 主入口
│   ├── ladder/                                  ← 階梯各級實作
│   │   ├── L0_sanity_check.m
│   │   ├── L1_sparse_warm_fit.m
│   │   ├── L2_full_warm_narrow.m
│   │   ├── L3_modal_only.m
│   │   └── L4_fallback.m                        ← 呼叫現行流程
│   ├── attribution/                             ← 誤差歸因
│   │   ├── test1_noise_floor.m
│   │   ├── test2_spatial_structure.m
│   │   ├── test3_modal_localization.m
│   │   └── generate_attribution_report.py
│   ├── template_management/                     ← 機型模板治理
│   │   ├── build_template_from_seed.m
│   │   ├── update_template_with_new_machine.m
│   │   ├── compute_robust_stats.m
│   │   └── template_schema_validator.py
│   ├── validation_experiments/                  ← A 階段實驗
│   │   ├── README_TW.md
│   │   ├── L0_repeat_fit.m
│   │   ├── L1_repeat_capture.m
│   │   ├── L2_pseudo_intervention.m
│   │   ├── L3_real_disassembly.m
│   │   ├── analyze_results.py
│   │   └── raw_data/                            ← 實驗影像存放
│   ├── per_machine_results/                     ← 每台機的校正結果
│   │   └── <machine_id>/
│   │       ├── PSF_fitted_2D_FOVstack.mat
│   │       ├── recalibration_log.csv
│   │       └── attribution_report.md
│   └── tests/                                   ← 單元測試
│       ├── test_ladder_logic.py
│       ├── test_template_schema.py
│       └── test_attribution_thresholds.py
│
├── machine_type_templates/                      ← 本設計新增
│   └── <model_id>/                              ← 例如 GMM_v1_NA023_M20x
│       ├── reference_template.mat
│       ├── reference_template.json
│       ├── source_machines/
│       │   ├── machine_001_seed.mat             ← R26NewPSF 種子機
│       │   └── ...
│       ├── visualizations/
│       └── MANIFEST.md
│
└── (其他現有資料夾不動)
```

### 12.2 命名慣例

| 檔案類型 | 命名規則 | 範例 |
|---|---|---|
| 設計文件(中文) | `DESIGN_TW.md` 或 `<TOPIC>_TW.md` | `DESIGN_TW.md` |
| 操作指南(中文) | `README_TW.md` | `README_TW.md` |
| MATLAB 入口腳本 | `run_<purpose>.m` | `run_quick_recalibration.m` |
| MATLAB 實作函式 | `<verb>_<noun>.m`(底線小寫) | `build_template_from_seed.m` |
| Python 工具腳本 | `<verb>_<noun>.py` | `generate_attribution_report.py` |
| 機型 ID | 駝峰或底線(包含 NA + M) | `GMM_v1_NA023_M20x` |
| 機台 ID | `machine_<3 位編號>` | `machine_001`, `machine_007` |

### 12.3 檔案職責表(避免功能重疊)

| 職責 | 唯一負責檔案 |
|---|---|
| 階梯流程的高階控制 | `run_quick_recalibration.m` |
| 階梯每一級的實作 | `ladder/L*.m` |
| 模板治理(建立、更新) | `template_management/*` |
| 歸因測試實作 | `attribution/test*.m` |
| 報告生成 | `attribution/generate_attribution_report.py` + `PSF_Report_Helper/recalibration_report.py` |
| 驗證實驗腳本 | `validation_experiments/*` |

---

## 13. 實施路線圖

### 13.1 兩個實施階段

| 階段 | 時間視窗 | 目標 |
|---|---|---|
| **A 階段:算法驗證** | 1–2 週 | 證明新方法在「同一台拆裝」可行,校準閾值 |
| **B 階段:跨機驗證** | 累積機台時 | 證明新方法跨同型號機台可行,模板進入成熟階段 |

### 13.2 A 階段 — 細部里程碑

| 里程碑 | 產出 | 驗收標準 |
|---|---|---|
| **A1. 模板基礎建設** | `template_management/` + 從 R26NewPSF 建立 v1.0.0 種子模板 | 模板檔案結構完整、能 reload |
| **A2. 階梯 L0+L4 實作** | `L0_sanity_check.m` + `L4_fallback.m` | L0 能 < 1 分產出 sanity report;L4 等價於現行流程 |
| **A3. 階梯 L1+L2 實作** | `L1_sparse_warm_fit.m` + `L2_full_warm_narrow.m` | 對種子機自身,L1+L2 能收斂到 ≈ L4 結果 |
| **A4. 階梯 L3 實作** | `L3_modal_only.m` | 同上,L3 收斂正常 |
| **A5. 歸因測試實作** | `attribution/test*.m` | 對種子機自身,所有測試正確判定 "no_real_change" |
| **A6. 驗證實驗執行** | 一天的 L0–L3 實驗 raw data | 完整 4 層資料 + metadata |
| **A7. 結果分析與閾值校準** | `validation_experiments/analyze_results.py` 輸出 | 階梯 / 歸因閾值定稿 |
| **A8. Acceptance review** | A 階段最終報告 | 滿足 §10.7 所有標準 |
| **A9. 上線準備** | `README_TW.md` 操作指南 + `run_quick_recalibration.m` 整合 | 操作者能獨立執行 |

### 13.3 B 階段 — 細部里程碑

| 里程碑 | 觸發條件 | 產出 |
|---|---|---|
| **B1. 第 2 台機校正** | 第 2 台同型號機到位 | 用 A 階段成果跑校正,人工 review,模板升級 early 階段 |
| **B2. 第 3-4 台機累積** | 持續到位 | 模板繼續累積,std 漸穩 |
| **B3. 進入 mature 階段** | 第 5 台機 + LOO std 穩定 | 模板版本升級到 v2.0.0,L3 完全可用 |
| **B4. 跨機 acceptance** | 累積 ≥ 5 台後 | 重新跑 §10.7 acceptance test,確認跨機表現符合預期 |
| **B5. 對外 deploy** | B4 通過 | 寫成正式 SOP,可移交產線使用 |

### 13.4 不在路線圖內的項目(明確排除)

- 自動化機型分類器(機型自動辨識)
- 多機型聯合先驗(用其他機型推未見過的機型)
- Active learning(自動建議下一台該量哪些 FOV)

這些是未來潛在擴充,**不在本設計的 scope 內**。

---

## 14. 開放問題與未來擴充

### 14.1 設計階段尚未回答的問題

| 編號 | 問題 | 為什麼 defer | 影響的章節 |
|---|---|---|---|
| OQ1 | L1 的 9 個 FOV 點是否該根據種子機的 PSF 變異度自適應選擇,而非固定位置? | 需要種子機的 PSF gradient 統計才能設計 | §7.3.1 |
| OQ2 | 種子階段的代理 std 倍率(2σ→4σ)是否需要因 Zernike 係數而異? | 需要 A 階段實驗實際看分佈再決定 | §8.3.2 |
| OQ3 | Test 2 用「同號比例」還是 Moran's I 較可靠? | 需 A 階段資料量化比較 | §9.4 |
| OQ4 | 如果新機被 L4 兜底,是否該允許其用「校準完的 PSF + outlier flag」上線? | 涉及產線政策,不是技術問題 | §7.6 |
| OQ5 | 機型模板要不要存「per-FOV 的 BADS warm-start 序列」加速 L2? | 額外複雜度高,效益不明 | §7.4 |

### 14.2 已知設計權衡(設計上做了取捨)

| 取捨 | 選擇 | 放棄了什麼 |
|---|---|---|
| Median+MAD vs Mean+std | Median+MAD | 大樣本下的統計效率 |
| 9 點固定位置 vs 自適應抽樣 | 固定位置 | 對特殊 PSF 結構的最佳覆蓋 |
| L3 只動 Z4/Z5/Z6 vs 全可解釋模態 | 只動 Z4/Z5/Z6 | 對 tilt 嚴重失準的捕捉 |
| 階梯固定升級條件 vs Bayesian 動態 | 固定條件 | 統計上的最優性 |
| MAT 為主 + JSON 鏡像 vs 純 JSON | MAT 為主 | Python 原生可讀性 |

### 14.3 可能的未來擴充方向

| 方向 | 觸發條件 | 描述 |
|---|---|---|
| 自適應抽樣(OQ1) | A 階段顯示 9 點覆蓋不足 | 根據種子機 PSF gradient 自動選 N 點 |
| 多機型聯合先驗 | 累積多個機型後 | 用機型 hierarchy 推未見過的相似機型 |
| Online template update | mature 階段穩定後 | 每台新機自動 incrementally 更新 std,不需 batch 重算 |
| 階梯動態跳級 | 實驗顯示某些情境可跳過 L1 直接 L2 | 根據 L0 結果預測該跳到哪級,進一步省時 |
| GUI 操作介面 | B 階段交付產線後 | MATLAB App 或 Web 介面,降低操作門檻 |

### 14.4 跟現行 PSF 政策可能衝突的點

| 衝突點 | 可能影響 | 處理建議 |
|---|---|---|
| 新方法的「機型 reference」與現行「formal PSF standard」是同一份還是兩份? | 治理混亂 | 機型 reference = formal standard 的衍生物,版本綁定 |
| 各台機的個體 PSF 是否進入 model 訓練? | 訓練資料一致性 | 個體 PSF 只用於該台機本地推論;訓練仍用 formal standard |
| 新方法產出的 PSF 是否能取代舊 checkpoint 嵌入的 PSF? | 重現性 | 不取代,只用於新 inference 流程 |

---

## 15. 附錄:術語對照與設計決策紀錄

### 15.1 中英術語對照

| 中文 | 英文 | 縮寫 |
|---|---|---|
| 機型模板 | Machine-Type Template | MTT |
| 快速校正 | Quick Recalibration | QR |
| 種子機 | Seed Machine | — |
| 種子階段 | Seed Stage | — |
| 早期階段 | Early Stage | — |
| 成熟階段 | Mature Stage | — |
| 階梯式校正 | Ladder-Based Recalibration | — |
| 誤差歸因 | Error Attribution | — |
| 噪聲基線 | Noise Floor | — |
| 假介入 | Pseudo Intervention | — |
| 真介入 | Real Intervention | — |
| 偽陽性率 | False Positive Rate | FPR |
| 真陽性率 | True Positive Rate | TPR |
| 模態定位 | Modal Localization | — |
| 可解釋模態 | Explainable Modes | — |
| 空間自相關 | Spatial Autocorrelation (Moran's I) | — |
| 中位數絕對離差 | Median Absolute Deviation | MAD |

### 15.2 設計決策紀錄(ADR-style)

#### ADR-1:選擇 Median+MAD 而非 Mean+std

**背景**:模板早期樣本少,易被 outlier 污染。
**決策**:主要統計量用 Median+MAD,Mean+std 為次要參考。
**後果**:大樣本下統計效率略低,但小樣本健壯性高。
**相關章節**:§6.3

#### ADR-2:階梯設 5 級而非 3 級或 7 級

**背景**:粒度權衡。
**決策**:5 級(L0–L4),L0 是 "no fit" 端,L4 是 "current pipeline" 端,中間 3 級提供漸進升級。
**後果**:閾值要校準的點較多,但每級職責清晰。
**相關章節**:§7

#### ADR-3:歸因方法用 3 個獨立測試串接,而非單一綜合 score

**背景**:可解釋性 vs 統計效率。
**決策**:3 個獨立測試,失敗即終止,可解釋性優先。
**後果**:統計效率略低,但結果易解釋、易 debug。
**相關章節**:§9

#### ADR-4:機型模板與快速校正流程分為兩個 artifact

**背景**:資料 vs 程式分離。
**決策**:模板存 .mat,流程存 .m,各自版本管理。
**後果**:多了一套 schema 與治理,但治理乾淨。
**相關章節**:§5.3

#### ADR-5:文件位置放 `PSF_Fitting/quick_recalibration/` 而非 `docs/superpowers/specs/`

**背景**:user 偏好優先(`PSF_Fitting/` 下開新區域)。
**決策**:遵循 user 指示,放 `PSF_Fitting/quick_recalibration/DESIGN_TW.md`。
**後果**:跟 superpowers 預設 spec 位置不同,但跟未來程式碼同地,操作上更直覺。
**相關章節**:本文件本身

### 15.3 修訂歷史

| 版本 | 日期 | 變更 |
|---|---|---|
| v0.1 (current) | 2026-04-18 | 初版,完整設計思路;尚未實作 |
