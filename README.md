# GMM_2_Final

2026-10-21研究保存入口：[各輪方法與GitHub取回](docs/reproducibility/README.md)／[逐輪問題、結果與來源](docs/reproducibility/EXPERIMENTS.md)／[本機全部值得保存內容的核對](docs/reproducibility/project_completion/README.md)。全專案補查仍在進行，已上傳、已核對與尚待完成的部分分別記錄。

最新保留原則是「保存生產方法，而非所有產物」：能重新生成的訓練資料等大檔，只留原程式、設定及必要來源，不要求先整套重建核對。不可再生的原拍、量測、人工標記與完整結果另外保存。[詳細取捨](docs/reproducibility/SOURCE_AND_IMAGE_DECISIONS.md)。

[訓練資料生產方法與來源](docs/reproducibility/GENERATION_GUIDE.md)已列出18條確認路線，分清R92與R93兩套共用基礎、原修正程式與在線觀測；177個範圍的原程式和設定另有索引。這批只補11份原來源／修正小紀錄約86KB，不新增資料集、影像或模型。

本輪改為**精選、輕量的研究整理**：保存原程式、設定與重做方法、文獻／文件、完整量測與比較表、關鍵模型及少量有明確用途的影像。舊全量大檔上傳已停止；大量訓練影像、逐張重建陣列和所有中途模型留在本機／H封存，只記錄來源與重建方式。既有大檔草稿已凍結，尚未刪除。依內容查找請從[專案地圖](docs/navigation/PROJECT_MAP.md#我現在要找什麼)進入。

[逐輪精選清單](docs/reproducibility/project_completion/curated/ROUND_CURATED_PLAN.md)列出177個研究／歷史範圍的用途及大小；本次補上完整位移表與必要光學常數共約3.35MB研究資料，關鍵模型及原論文圖引用既有內容，不再整批重傳。

[早期重建精選與完整數表](docs/reproducibility/project_completion/curated/EARLY_RECON_SELECTION.md)已將R33至COMBO的10套逐張輸出改為34張原圖及歷史入口，保留140份完整量測。一般閱讀內容少約5.55GB；既有歷史與本機原件保留，沒有刪版本附件。

[早期失敗到後續設計的閱讀入口](docs/reproducibility/project_completion/curated/FAILURE_LINEAGE_READING.md)另將R100／R103／R104的130份完整原結果直接保留於一般版本；三張原比較圖與三個原選用模型引用既有內容。曝光失敗、SEM較差結果及共用拍攝界線一併說明，不新增整批影像或模型。

目前論文使用R152／RAW，十方法完整比較及圖表見[最新論文交接](Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)。正式使用基準仍是COMBO；歷史模型、較早論文與正在訓練的版本各自保留身分。

這份文件是整個專案的**入口總覽**。如果你是第一次接觸這個專案，從這裡開始讀。
This is the top-level overview for the project. If you are new, start here.

專案控制與整體巡檢請使用 `python Tools/project_control_center.py`；它是官方控制入口，但不是新的真相來源。

---

## 目錄 / Table of Contents

1. [專案是在做什麼 / What This Project Does](#專案是在做什麼--what-this-project-does)
2. [核心名詞速查 / Key Terminology](#核心名詞速查--key-terminology)
3. [目前 Baseline / Current Baseline](#目前-baseline--current-baseline)
4. [閱讀順序 / Reading Order](#閱讀順序--reading-order)
5. [目錄結構 / Directory Structure](#目錄結構--directory-structure)
6. [系統整體流程 / System Pipeline Overview](#系統整體流程--system-pipeline-overview)
7. [延伸連結 / More Docs](#延伸連結--more-docs)

---

## 專案是在做什麼 / What This Project Does

### 白話版說明

這個專案的長期目標是：讓顯微鏡影像中的各種結構，在重建後能保留正確的邊界位置與細節。環形結構（annulus）是目前最完整、最可比較的正式測試代理，但不是唯一關心的顯微結構。

更具體地說——
顯微鏡拍出來的影像因為光學模糊（PSF 效應），邊界形狀會失真。我們訓練一個 AI 超解析模型（`GeoEdgeAlignSR`），讓它把這層模糊還原，並讓還原後的影像「更有利於下游幾何匹配工具（GMF）做穩定的幾何定位」。

**重要：這不是普通的影像銳化專案。** 視覺上「看起來更清晰」不等於「幾何定位更準」。正式 baseline 的最終驗收仍看外部 GMF 在三尺度環形資料上的 step std；R39-R43 另外開出顯微泛化研究線，用來探索格線、紋理、缺陷、曲線與混合場景的通用邊界忠實度。

### Technical Version

The long-term goal is faithful geometric reconstruction of microscopy structures. Annulus data is the current formal external gate because it has stable historical GMF comparisons, but it is a proxy for the broader microscopy-boundary objective.

The optimization target is not generic visual sharpness.
It is: **whole-annulus GMF geometry** — how well the reconstructed image supports the downstream geometric matching function (GMF) in localizing the annulus boundary at multiple displacement scales.

Key performance metrics (all from the external GMF evaluator):

| Scale | What It Tests | Primary Status |
|-------|--------------|----------------|
| `8px` macro | Large-scale tracking stability guard | Must not regress |
| `0.8px` mid | **Main battlefield** — medium-scale precision | Hard improvement target |
| `0.08px` tiny | Sub-pixel precision | Useful but not decisive alone |

---

## 核心名詞速查 / Key Terminology

| 名詞 | 白話解釋 / Plain Explanation |
|------|------------------------------|
| **PSF（點擴散函數）** | 顯微鏡光學模糊的數學描述。PSF 越準確，模型去模糊越有依據。<br>Mathematical description of the microscope's optical blur. Accurate PSF = better deblurring. |
| **GMF（幾何匹配函數）** | 外部幾何定位評分工具。GMF 分越好（step std 越小），代表模型輸出對邊界定位越有幫助。<br>External geometric evaluator. Lower step std = better boundary localization. |
| **external compare** | 用訓練好的模型重建真實影像後，送 GMF 打分，與 baseline 比較的最終驗收流程。<br>The final acceptance test: reconstruct real images, run GMF, compare with baseline. |
| **internal audit** | 在合成資料上做的初篩稽核（pairmix_algblend、edge_band_refine 探針）。通過 internal audit 是必要條件，但不等於外部成功。<br>A synthetic-data screening step. Necessary but not sufficient. |
| **baseline / COMBO** | 目前正式的 production baseline，是 `r38v2_8px_gate_p95`（COMBO）。它是 Winsorize + seq 8px gate + warmup 的最均衡組合。<br>The current formal production baseline is `r38v2_8px_gate_p95` (COMBO). |
| **checkpoint（.pth.tar）** | 模型訓練途中儲存的參數快照。`best_tradeoff.pth.tar` 是整體指標最均衡的那份。<br>A saved snapshot of model weights. `best_tradeoff.pth.tar` is the primary checkpoint used. |
| **sandbox** | 隔離的實驗目錄，讓新的研究方向不影響主線穩定工作流程。<br>An isolated experiment directory, keeping research changes away from the stable mainline. |
| **step std** | 連續幀之間位移差的標準差。越小 = 定位越穩定。<br>Standard deviation of displacement differences between frames. Smaller = more stable localization. |
| **Whole-FOV PSF** | 對全視野（FOV）100 個格點位置各自擬合出的 PSF 集合。<br>A 10×10 grid of fitted PSFs covering the full field of view. |

---

## 目前 Baseline / Current Baseline

Formal production baseline: **COMBO / r38v2_8px_gate_p95** (effective 2026-04-08).
Round30 is the historical former baseline (歷史前任 baseline).
See `PROJECT_STATE.md` for full current state, numbers, and working rules.

---

## 閱讀順序 / Reading Order

從 `PROJECT_STATE.md` 開始（前 50 行 Quick Handoff 區 3 分鐘讀完）。完整文件責任邊界與延伸文件見 `docs/README.md`。

- 想看現況 / 接手 → `PROJECT_STATE.md`
- 想看穩定規則 → `PROJECT_ARCHITECTURE.md`
- 機器可讀 decision truth → `ESTIMATOR_POLICY.json`
- 完整歷史敘事 → `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

---

## 目錄結構 / Directory Structure

```text
D:\GMM_2_Final\
│
├── README.md                          ← 你現在在看這份（入口總覽）
├── PROJECT_STATE.md                   ← 現況 + handoff + working rules
├── PROJECT_ARCHITECTURE.md            ← 穩定架構與決策規則
├── ESTIMATOR_POLICY.json              ← 機器可讀 decision control plane
├── REPO_GOVERNANCE.md                 ← Git/GitHub 治理規則
├── CONTRIBUTING.md                    ← 貢獻指南
├── AGENTS.md                          ← AI agent 協作規則
├── CLAUDE.md                          ← Claude Code 設定
│
├── Model/                             ← AI 模型核心（訓練 + 推論）
│   ├── README.md                      ← Model 模組完整說明
│   ├── GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py     ← 模型定義
│   ├── GeoEdgeAlignSR_v1_Train_*.py               ← 訓練入口
│   ├── GeoEdgeAlignSR_v1_Infer_*.py               ← 推論入口
│   └── ... (training / audit / external compare scripts)
│
├── PSF_Fitting/                       ← PSF 擬合流程（MATLAB）
│   ├── README.md                      ← PSF 模組完整說明
│   ├── HDR_fitting_2D_WholeFOV.m      ← 全 FOV 批次 PSF 擬合（正式入口）
│   └── Crop_circle_FreqFiltered/Fits/ ← 正式 PSF 輸出
│
├── Tools/                             ← 控制中心 + 驗證腳本
│   ├── project_control_center.py      ← 官方控制入口
│   └── validate_project_structure.py  ← 結構驗證
│
├── AnalysisLab/                       ← 常駐分析資料入口
│
├── Experiments/                       ← 獨立實驗與正式候選 surface
│   ├── R33RobustLoss/                 ← GMF extreme alternate
│   ├── R38v2SeqFixed/                 ← formal baseline（COMBO）+ visual priority alternate
│   ├── R32Sandbox/                    ← Round32 隔離沙盒（已關閉）
│   └── R26NewPSFCheck/                ← open PSF side track
│
├── Training_Data/                     ← 訓練資料（不追蹤）
├── Traing_Progress/                   ← 訓練輸出（不追蹤；注意拼字）
│
├── docs/                              ← 研究文件、證據、政策、歷史
│   ├── README.md                      ← docs 區入口
│   ├── navigation/PROJECT_MAP.md      ← 跨工作區檔案與正式入口地圖
│   ├── operations/                    ← 操作指引（新實驗 SOP、quirks、治理）
│   ├── analysis/                      ← 研究路徑圖
│   ├── evidence/                      ← 策展後的證據引用錨點
│   ├── history/                       ← 完整歷史敘事
│   ├── policy/                        ← 正式政策（PSF 等）
│   └── archive/legacy_runtime_status/ ← 封存的 R20-R32 legacy root status 快照
│
└── _deployment_package/               ← R26 正式交付封包（不追蹤）
```

> **注意**：`Traing_Progress/` 資料夾名稱故意保留拼字錯誤（少一個 i），這是歷史遺留，所有程式都依賴這個路徑，請勿更名。
> **Note**: The `Traing_Progress/` folder name has a known typo (missing one `i`). This is intentional for historical compatibility — all scripts depend on this exact name.

---

## 系統整體流程 / System Pipeline Overview

整個系統由三個主要模組組成，環環相扣：
The system has three interlocking modules:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 0：PSF 擬合 / PSF Fitting（MATLAB）                                     │
│                                                                              │
│  顯微鏡影像 ──▶ [BADS 最佳化 + Zernike 像差模型] ──▶ PSF_fitted_2D_FOVstack.mat │
│                                                                              │
│  入口：PSF_Fitting/HDR_fitting_2D_WholeFOV.m                                 │
│  輸出：PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat  │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │ 讀取 PSF / reads PSF
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 1：模型訓練 / Model Training（Python + PyTorch）                         │
│                                                                              │
│  訓練影像 + PSF ──▶ [GeoEdgeAlignSR U-Net + Wiener 物理層] ──▶ checkpoint     │
│                                                                              │
│  模型特色：                                                                   │
│    • PSFDeconvPhysics：在 U-Net 前做 Wiener 反捲積（物理先驗）               │
│    • WeakPSFDeconvBlock：Decoder 端軟混合多 PSF 去模糊注入                   │
│    • ShiftSafeUpsample：Anti-aliasing 上採樣，抑制 checkerboard             │
│    • OpticalBandpassFilter：訓練期限制超物理頻率（推論時自動關閉）           │
│                                                                              │
│  入口：Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py     │
│  輸出：Traing_Progress/training_progress_{...}/weights/best_tradeoff.pth.tar │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
┌─────────────────────────┐     ┌────────────────────────────────────────────┐
│  STEP 2A：Internal Audit │     │  STEP 2B：External GMF Compare            │
│  （內部探針稽核）          │     │  （外部真實資料驗收）                        │
│                          │     │                                            │
│  合成資料探針：           │     │  1. 用 checkpoint 重建 NTU 真實影像        │
│  • 0.8px pairmix probe  │     │  2. 送 GMF 工具計算 step std               │
│  • 8px guard probe      │     │  3. 與 baseline 比較 3 個 pitch 尺度       │
│                          │     │                                            │
│  通過 = 有資格進外部驗收  │     │  **唯一最終裁判** — 不可被 internal 取代   │
│  未通過 = 直接淘汰       │     │  通過 → 升級 baseline                      │
│                          │     │  失敗 → 保留現 baseline，不得升級          │
└─────────────────────────┘     └────────────────────────────────────────────┘
```

### 訓練 Loss 組成（模型不只學視覺銳利度）

| Loss 項目 | 權重 | 說明 |
|----------|------|------|
| 像素重建（L1/MSE） | 1.0 | 基礎重建品質 |
| 梯度幅值（Sobel） | 0.8 | 邊緣對比保真 |
| 邊緣方向一致性 | 0.3 | 防止邊緣方向漂移 |
| 平移等變幾何（EQ） | 0.5 | 讓模型對 sub-pixel 平移保持幾何一致 |
| 統計/頻帶一致性 | 0.10+0.10 | 整體統計特性穩定 |
| 高頻 Laplacian | 0.15 | 細節恢復 |

---

## 延伸連結 / More Docs

| 主題 | 去哪看 |
|------|--------|
| 研究歷程圖 / research path map | `docs/analysis/RESEARCH_PATHS.md` |
| 升級 baseline 條件、新 round 立案規則 | `PROJECT_ARCHITECTURE.md` |
| 分支策略、同步政策、追蹤範圍 | `REPO_GOVERNANCE.md` |
| 文件責任邊界、docs 區導覽 | `docs/README.md` |
| 不知道內容位於哪個工作區 | `docs/navigation/PROJECT_MAP.md` |
| 開新實驗完整指南（命名 / 模板 / SOP） | `docs/operations/STARTING_NEW_EXPERIMENT.md` |
| AI agent 行為契約 | `CLAUDE.md` / `AGENTS.md` |
| 整體巡檢（控制中心）| `python Tools/project_control_center.py` |
| Legacy R20-R32 root status 快照 | `docs/archive/legacy_runtime_status/` |

GitHub 研究控制台：`https://github.com/users/rio10255254/projects/1`
