# R26NewPSFCheck — 實驗 Sandbox 說明文件

> 最後更新：2026-03-26
>
> 註：本文件主要記錄 2026-03-26 這輪 sandbox 的歷史執行狀態。
> 2026-03-27 之後的 `current standard` / `legacy baseline` 政策，
> 請以 `docs/policy/PSF_POLICY_TRANSITION_R26.md`
> 與 `docs/policy/PSF_STANDARD_POLICY.json` 為準。
>
> 本文件描述的是 sandbox 的**完整本地執行面**，不是 Git-tracked surface 的一比一清單。
> checkpoint snapshots、GMF drop-ins、package clone、cleanup archives 等 bulk 內容在本地可能存在，
> 但不一定會被追蹤進 GitHub。

---

## 1. 這個實驗在做什麼

這個資料夾是一個**獨立的實驗沙盒（sandbox）**，負責承接兩件彼此相關、但各自獨立的工作：

### 工作一：驗證「換用新 PSF 重訓後的模型」效果是否真的更好

我們的 AI 模型（GeoEdgeAlignSR）在訓練時會讀入一份描述顯微鏡光學特性的檔案，稱為 **PSF**（點擴散函數，Point Spread Function）。這份 PSF 告訴模型「顯微鏡會怎麼把光學影像模糊掉」，讓模型能夠針對性地把影像還原清晰。

2026-03-26，我們完成了一版新的 PSF 擬合結果（使用全視野 100 個位置的量測重新計算），並以這份新 PSF 從頭重新訓練了模型。**本 sandbox 的第一個目標**，就是拿這次重訓出來的新模型，去跑三種不同尺度（Pitch 1μm / 0.1μm / 0.01μm）的外部資料集重建，等待外部 GMF（幾何匹配函數，Geometric Matching Function）評分工具打分，再與舊版封包正式效果做客觀比較。

### 工作二：審核 PSF 擬合正式流程是否有執行層面的問題

在新 PSF 擬合完成後，我們需要確認根專案 `PSF_Fitting/` 底下的正式流程本身沒有損壞或自相矛盾。**本 sandbox 的第二個目標**，是在不覆寫正式輸出的前提下，對 PSF 正式流程做一次可追溯的審核。

> **白話小結：** 這個資料夾同時在回答兩個問題——「用新 PSF 訓練的模型有比舊版好嗎？」以及「PSF 的擬合程式現在有沒有問題？」

---

## 2. 名詞簡介

閱讀本文件前，先了解幾個關鍵名詞，方便後面的說明：

| 名詞 | 白話解釋 |
|------|---------|
| **PSF（點擴散函數）** | 顯微鏡對一個極小光點成像時，實際拍到的模糊光暈形狀。它代表了顯微鏡的光學模糊特性。PSF 越準確，模型對影像的還原就越有依據。 |
| **PSF 擬合** | 透過讓模擬影像不斷逼近實際量測影像，反推出最符合現實的 PSF 形狀。本專案使用 MATLAB + BADS 最佳化演算法完成這件事。 |
| **Whole-FOV PSF** | 對全視野（Field of View）100 個格點位置分別擬合的 PSF 集合，存在 `PSF_fitted_2D_FOVstack.mat` 裡。由於顯微鏡的光學像差在視野不同位置略有差異，Whole-FOV 版比單張版更能反映真實狀況。 |
| **GeoEdgeAlignSR（模型）** | 本專案的 AI 超解析模型，全名 `GeoEdgeAlignSR_v1_v5_NoCoord`。它在 U-Net 骨幹前加了一層物理反捲積，利用 PSF 預先還原光學模糊，再用深度學習進一步提升解析度。 |
| **checkpoint（.pth.tar）** | 模型訓練完一段時間後儲存下來的「快照」，包含所有神經網路參數。`best_tradeoff.pth.tar` 是訓練過程中整體指標最均衡的那個快照，也是推論時預設使用的版本。 |
| **R26 / r26_sm035** | 本專案的第 26 次正式交付版（Release 26）。`r26_sm035` 是這次交付時，使用平滑強度 `sm035` 訓練出的正式模型名稱，代表封包內目前的「基準線」效果。 |
| **external recon（外部重建）** | 用指定 checkpoint 對一組外部資料集（NTU 外部影像資料集，三個不同 pitch 尺度）做推論重建，產出重建影像供 GMF 評分。 |
| **GMF（幾何匹配函數）** | 外部評分工具，專門量化重建影像在幾何精度上的表現。GMF_score.txt 是它輸出的分數檔，分數越高代表幾何對齊越好。目前 GMF 工具由外部團隊執行，需要等待結果回填。 |
| **odd-frame（奇幀）** | 外部資料集的影像依奇偶分組，本次推論只跑奇數幀（odd），作為 GMF 評分的標準輸入。 |
| **formal_config.json** | PSF 擬合正式輸出目錄下的設定紀錄，記載這次擬合使用的參數組合（如 warm_start、pre_alignment、lock_tilt）以及 promoted 的候選來源，作為可追溯依據。 |

---

## 3. 為什麼要建在獨立 Sandbox，不直接在交付封包裡做

### 問題背景

本專案有一份正式交付封包，位於：

```
Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包
```

這份封包記錄了 R26 正式交付的完整狀態，包含訓練輸出、推論輸出、分析報告等，具有**「交付版本語意」**——也就是說，它的內容代表了「我們正式提交給對方的成果」。

### 為什麼不能直接在封包裡改

如果把「以新 PSF 重訓的模型」和「新 PSF 的相關比較實驗」全都混進封包的主目錄，會出現兩個問題：

1. **污染交付語意**：封包的主結構本來只應該包含正式交付的內容。一旦把研究過程中的中間產物（如新 PSF 重訓的 checkpoint、中間比較報告）混進去，就很難區分「哪些是正式交付的結果」、「哪些是後續研究的輸出」。
2. **難以追溯**：日後若需要重現封包的交付狀態，或把封包移交他人，「正式交付內容」與「後續研究輸出」混在一起會造成混亂。

### 本 Sandbox 的做法

- 把新訓練的 checkpoint **複製快照**到本 sandbox 的 `artifacts/` 資料夾，作為本次實驗的輸入。
- 所有外部重建的輸出、比較報告、PSF 審核記錄，**全部只落在本 sandbox**（`Experiments/R26NewPSFCheck`），不再寫回封包。
- 封包本身只被當成**來源**，不被當成輸出目的地。

這樣一來，封包維持乾淨的交付語意，本 sandbox 則承載所有後續的研究與比較工作。

---

## 4. 整體工作流程

本 sandbox 涵蓋的完整工作流程如下，共七個步驟：

```
步驟 1：新 PSF 擬合完成
    └── PSF_Fitting/ 正式輸出 PSF_fitted_2D_FOVstack.mat
         │
步驟 2：以新 PSF 重新訓練模型（在封包內執行）
    └── 封包內訓練輸出新 checkpoint（best_tradeoff.pth.tar）
         │
步驟 3：將新 checkpoint 複製到 sandbox
    └── artifacts/newpsf_r26_retrain/weights/best_tradeoff.pth.tar
         │
步驟 4：執行 external recon（三尺度外部重建）
    └── 使用 Tools/run_external_recon_newpsf.ps1
    └── 輸出到 external_compare/newpsf_r26_retrain/
         │
步驟 5：等待外部 GMF 打分（此步驟需人工）
    └── 把重建影像交給外部 GMF 工具
    └── 將 GMF_score.txt 放回 gmf_results/raw/ 對應目錄
         │
步驟 6：新舊效果比較（Demo 單張分析）
    └── 已完成，見 reports/new_psf_retrain_compare_20260326.md
         │
步驟 7：PSF 正式流程審核
    └── 已完成，見 psf_audit/PSF_FORMAL_AUDIT_20260326.md
```

目前已完成步驟 1–4 與步驟 6–7，步驟 5（等待外部 GMF 結果）尚在進行中。

---

## 5. 目錄結構

```
R26NewPSFCheck/
│
├── README.md                            ← 本文件，sandbox 的完整說明
│
├── artifacts/                       ← 本地 checkpoint 快照（local-only，不追蹤）
│   └── newpsf_r26_retrain/
│       ├── weights/
│       │   └── best_tradeoff.pth.tar   ← 新 PSF 重訓最佳 checkpoint 快照
│       └── training_meta/              ← run_meta.json 與 validation log 快照
│
├── external_compare/
│   └── newpsf_r26_retrain/             ← 外部三尺度重建的工作目錄
│       ├── batch_manifest.json         ← 記錄本次重建使用的 checkpoint、資料集、時間戳記
│       ├── gmf_results/             ← 外部 GMF drop-in 位置（local-only，不追蹤）
│       │   └── raw/
│       │       ├── pitch8px/           ← 等待 GMF_score.txt 回填（對應 Pitch1um_Y_100）
│       │       ├── pitch0p8px/         ← 等待 GMF_score.txt 回填（對應 Pitch0.1um_Y_60）
│       │       └── pitch0p08px/        ← 等待 GMF_score.txt 回填（對應 Pitch0.01um_Y_40）
│       └── reconstruct_progress_best_tradeoff_in_Cropped_Output_{timestamp}/
│           └── （三個資料集的推論輸出影像）
│
├── reports/
│   ├── new_psf_retrain_compare_20260326.md  ← 新 PSF 重訓 vs 舊 R26 的 Demo 單張效果比較報告
│   └── STATUS_20260326.md                   ← sandbox 整體進度摘要
│
├── psf_audit/
│   └── PSF_FORMAL_AUDIT_20260326.md    ← PSF 正式擬合流程的完整審核記錄
│
├── formal_newpsf_candidate/            ← 以 r26_sm035 recipe 為基底、只換 PSF 的候選驗證資料
│   ├── candidate_manifest.json         ← hash 記錄、來源路徑、promote 歷程
│   ├── package_clone/                  ← candidate smoke 驗證用的封包副本（local-only，不追蹤）
│   └── reports/
│       └── NEW_PSF_FORMAL_R26_COMPARE.md  ← new-vs-legacy promotion 比較摘要
│
├── ablation_single_sample/             ← 單樣本消融實驗（新舊 checkpoint 在同張圖的對比）
│   ├── input/                          ← 消融用的輸入影像
│   └── reconstruct_progress_*/         ← 新版與舊版各自的推論輸出
│
├── pure_psf_control/                   ← 純 PSF 控制組實驗目錄
│
├── root_cause_centering/               ← 退步根因分析實驗目錄
│
├── runtime/                            ← 執行期暫存（腳本執行中產生的臨時檔案）
│
├── package_policy_transition/          ← 封包政策轉換相關存檔（local-only，不追蹤）
├── package_repro_validation/           ← 封包可重現性驗證存檔
├── policy_transition_archive_*/        ← 政策轉換的封存快照
├── package_cleanup_release_archive_*/  ← 封包清理與 release 的歷史存檔
│
└── Tools/
    ├── run_external_recon_newpsf.ps1   ← 執行外部三尺度重建的主腳本
    └── package_cleanup_20260326.ps1    ← 封包清理輔助腳本
```

### 各主要資料夾的白話說明

**`artifacts/`**
存放從封包複製過來的 checkpoint 快照。這裡的 `best_tradeoff.pth.tar` 是本次實驗的**起點**：它是以新 PSF 重訓後，整體表現最均衡的那個模型存檔。這一層屬於本地 execution surface，**不作為 Git-tracked sandbox surface 的必要部分**。

**`external_compare/`**
外部重建和 GMF 評分的工作目錄。分三個 pitch 尺度分別存放重建輸出，並預留了等待 GMF_score.txt 回填的位置。外部 GMF 工具的運算結果需要人工對接，完成後才能進行正式的新舊比較。`gmf_results/raw/` 屬於本地 drop-in surface，**預設不追蹤進 Git**。

**`reports/`**
本次實驗的分析報告。目前有兩份：一份是「新 PSF 重訓 vs 舊 R26」在 Demo 影像上的詳細比較（已完成），另一份是整體進度摘要。

**`psf_audit/`**
PSF 正式擬合流程的審核記錄。記錄了對 `PSF_Fitting/` 根目錄程式邏輯、測試、ValidationLab 聚合結果的逐項檢查結論。

**`formal_newpsf_candidate/`**
這個資料夾的責任更窄、更嚴格：它只測試「在完全不改動訓練 recipe 的前提下，只把 PSF 換成新版」這一個變量，確認新 PSF 封包是否可以正常使用，並形成正式 promote 的來源記錄。`package_clone/` 屬於本地 smoke 驗證副本，**不屬於 Git-tracked minimal evidence surface**。

**`Tools/`**
本 sandbox 專用的重跑腳本，主要是 `run_external_recon_newpsf.ps1`。

---

## 6. 如何重跑外部三尺度重建

如果你需要重新執行外部重建（例如使用不同的 checkpoint），請使用以下腳本：

### 腳本位置

```
Experiments/R26NewPSFCheck/Tools/run_external_recon_newpsf.ps1
```

### 基本用法（使用預設 checkpoint）

在 PowerShell 中執行：

```powershell
Set-Location Experiments/R26NewPSFCheck/Tools
.\run_external_recon_newpsf.ps1
```

預設會使用：

```
Experiments/R26NewPSFCheck/artifacts/newpsf_r26_retrain/weights/best_tradeoff.pth.tar
```

### 指定自訂 checkpoint

```powershell
.\run_external_recon_newpsf.ps1 `
    -WeightsPath "path\to\your\best_tradeoff.pth.tar" `
    -CandidateName "your_candidate_name"
```

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `-PythonExe` | Python 執行檔路徑 | `C:\Users\Rio\anaconda3\python.exe` |
| `-WeightsPath` | checkpoint 路徑 | sandbox 內 `artifacts/` 的預設快照 |
| `-CandidateName` | 輸出子資料夾名稱 | `newpsf_r26_retrain` |

### 腳本會做什麼

1. 自動解析 sandbox 根目錄與專案根目錄的路徑。
2. 呼叫根專案的 `Tools\RunRepresentativeExternalRecon.ps1` 共用工具，對三個外部資料集依序執行推論。
3. 自動建立 `gmf_results/raw/pitch8px/`、`pitch0p8px/`、`pitch0p08px/` 等目錄。
4. 執行完畢後印出三個 GMF_score.txt 的預期放置路徑。

### 重建的三個資料集

本次重建對象是 NTU 提供的三尺度外部資料集，只跑奇數幀（odd-frame）：

| 資料集名稱 | 輸入路徑 | GMF pitch 對應 |
|-----------|---------|--------------|
| `Pitch1um_Y_100` | `C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output` | `pitch8px` |
| `Pitch0.1um_Y_60` | `C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.1um_Y_60\Cropped_Output` | `pitch0p8px` |
| `Pitch0.01um_Y_40` | `C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.01um_Y_40\Cropped_Output` | `pitch0p08px` |

本次已完成重建的時間戳記為 `20260326_115148`，輸出位於：

```
Experiments/R26NewPSFCheck/external_compare/newpsf_r26_retrain
reconstruct_progress_best_tradeoff_in_Cropped_Output_20260326_115148\
```

---

## 7. 關鍵結果摘要：新 PSF 重訓 vs 舊版 R26

> 完整報告：`reports/new_psf_retrain_compare_20260326.md`

本次在封包內使用新 PSF 完成重訓後，以**相同的 Demo 影像、相同的 ROI 座標、相同的評估指標定義**，對新舊兩版模型做了並排比較。

### 新 PSF 重訓流程

1. 從根專案 `PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat` 取用當時根專案正式 PSF（SHA256: `F54F75F191AFEE507EA7BE9F5B561A465590A94DFDDD72EF722818D48E82E673`）。
2. 將封包內舊 PSF 備份後替換（舊版 SHA256: `3AAB9CC1ED9EE0EB9C85227D026A3A8D86D0C035B8D06A46EB688551EFAE79CD`）。
3. 使用封包內既有訓練腳本執行完整重訓（訓練開始時間：`2026-03-26 09:32:23`，GPU: NVIDIA RTX A6000）。
4. 以重訓後的 `best_tradeoff.pth.tar`（存檔時間：`2026-03-26 09:41:32`）對 Demo_Input 做推論。
5. 以舊版相同的 ROI 座標覆寫新版分析，確保新舊比較公平。

### 單張 Demo 影像指標對照表

> `delta = 新版 - 舊版`，負值代表退步（對於邊界斜率、CNR 等越大越好的指標），正值代表退步（對於邊界寬度等越小越好的指標）。

| 指標 | 說明 | 舊版 R26 | 新 PSF 重訓 | delta | 判讀 |
|------|------|--------:|----------:|------:|------|
| `edge_width_main_px` | 主邊界寬度（越小越好） | 33.47 | 36.26 | +2.79 | 退步 |
| `edge_width_weak_px` | 弱邊界寬度（越小越好） | 34.01 | 49.08 | +15.07 | 明顯退步 |
| `max_slope_main` | 主邊界最大斜率（越大越好） | 6.45 | 4.39 | −2.06 | 退步 |
| `max_slope_weak` | 弱邊界最大斜率（越大越好） | 5.29 | 2.08 | −3.21 | 明顯退步 |
| `CNR_main` | 主邊界局部對比（越大越好） | 19.55 | 9.19 | −10.36 | 明顯退步 |
| `CNR_weak` | 弱邊界局部對比（越大越好） | 33.34 | 7.79 | −25.55 | 嚴重退步 |
| `background_std` | 背景波動（越小越好） | 0.65 | 1.09 | +0.44 | 退步 |
| `background_grad_p95` | 背景高梯度（越小越好） | 3.16 | 3.16 | ±0.00 | 持平 |
| `HF_ratio` | 固定高頻帶能量佔比 | 0.0103 | 0.0164 | +0.006 | 不宜直接視為優勢 |
| `checkerboard_ratio` | 棋盤格傾向（越小越好） | 0.121 | 0.215 | +0.094 | 退步 |
| `edge_continuity_ratio` | 邊緣連續性（越大越好） | 0.994 | 0.267 | −0.728 | 嚴重退步 |
| `ring_thickness_std_px` | 環厚度一致性（越小越好） | 4.25 | 1.55 | −2.70 | **改善** |

### 解讀

**這次 Demo 單張的結論很明確：新 PSF 重訓版整體不如舊版 R26。**

退步集中在以下幾個方面：

- **邊界集中化退步**：邊界寬度變寬、最大斜率下降，代表模型輸出的邊界「比較模糊」。
- **對比度下降**：CNR（訊雜比）在主邊界和弱邊界都大幅下降，背景波動也上升。
- **假高頻傾向增加**：`checkerboard_ratio` 升高，代表輸出有更多棋盤格類偽影。
- **邊緣連續性嚴重下降**：`edge_continuity_ratio` 從 0.994 掉到 0.267，非常顯著。

唯一的正向訊號是 `ring_thickness_std_px`（環厚度標準差）下降，代表幾何厚度更均勻。但這一項的改善，不足以蓋過上述所有指標的退步。

### 目前的解讀與建議

目前這個退步，更可能的原因是**「新 PSF + 舊訓練 recipe 的組合不合適」**，而不是新 PSF 本身的物理結果有誤。具體來說，可能的因素包括：
- `best_tradeoff` 這個 checkpoint 選模準則是為舊 PSF 時代設計的，對新 PSF 不一定最優。
- Loss 的各項權重（`W_REC`、`W_GRADMAG` 等）可能需要針對新 PSF 重新調整。
- 最佳 checkpoint 不一定在 `best_tradeoff`，可能在 `best_detail_guarded` 或其他 epoch。

**不建議只看這張 Demo 圖就下最終結論。應等待外部三尺度 GMF 分數回來後，再做整體評估。**

---

## 8. PSF 正式流程審核結論

> 完整報告：`psf_audit/PSF_FORMAL_AUDIT_20260326.md`

在完成上述 Demo 比較的同時，也對根專案 `PSF_Fitting/` 正式流程做了一次全面審核，確認程式邏輯、設定檔與測試是否一致。審核項目如下：

### 審核項目 1：正式入口與 formal_config.json 是否一致

- `HDR_fitting_2D_WholeFOV.m`：目前只是一個薄包裝（thin wrapper），直接呼叫 `HDR_fitting_2D_WholeFOV_impl()`。
- `HDR_fitting_2D_WholeFOV_impl.m`：預設參數為 `warm_start = true`、`pre_alignment = true`、`lock_tilt = true`、`prealign_search_step = 0.25`、`output_root = Crop_circle_FreqFiltered/Fits`。
- `Crop_circle_FreqFiltered/Fits/formal_config.json`：記載的設定與上面程式邏輯一致，且 formal candidate 來源仍指向 ValidationLab 的 reasonable candidate。

**結論：文件與程式一致，沒有「說一套、跑另一套」的矛盾。**

### 審核項目 2：Python 測試

執行命令：
```powershell
pytest PSF_Fitting/tests/python/test_report_analysis.py -q
```
結果：**6 passed in 1.80s**。

### 審核項目 3：ValidationLab 聚合重建

執行命令：
```powershell
Set-Location PSF_Fitting/PSF_Fitting_ValidationLab
.\run_validation_lab.ps1 -AggregateOnly
```
結果：aggregate 成功重建比較圖、figures 與 reports，`best_overall_experiment = alignment_quarter_rep16`。

**結論：ValidationLab 的既有實驗輸出可被重新聚合，promotion 所依賴的比較鏈沒有損壞。**

### 審核項目 4：MATLAB Smoke Tests

執行命令：
```powershell
matlab -batch "cd('PSF_Fitting'); run('tests/run_matlab_smoke_tests.m')"
```
結果：**All MATLAB smoke tests completed. 共 11/11 通過。**

注意：過程中出現 BADS 的 bounds warning（`Plausible lower/upper bounds PLB and/or PUB not specified`），這是一個已知的既有提示訊息，不會導致 formal flow 中斷或輸出錯誤，暫時不需要處理。

### 審核總結

| 審核項目 | 結果 |
|---------|------|
| 正式入口與 formal_config.json 一致性 | ✓ 一致 |
| Python 測試 | ✓ 全通過 |
| ValidationLab 聚合重建 | ✓ 可重建 |
| MATLAB Smoke Tests | ✓ 11/11 通過 |

**目前 PSF 正式擬合流程在執行層面沒有可見的問題。**

這並不代表「新 PSF + 模型重訓」的下游效果一定好，那是另一個問題。本審核只確認了 `PSF_Fitting/` 的程式本身沒有損壞。

---

## 9. 外部 GMF 對接說明

### 什麼是 GMF，為什麼要等它

GMF（幾何匹配函數）是一個外部評分工具，專門量化重建影像在幾何精度上的分數。它的輸入是重建影像，輸出是 `GMF_score.txt` 分數檔。

為什麼不能只看 Demo 圖的指標就下結論？因為 Demo 圖只是一張訓練或展示用的單張影像，而 GMF 測試集是三種完全不同物理尺度的外部量測資料（從 1μm Pitch 到 0.01μm Pitch），能更客觀地反映模型在實際使用場景下的幾何精度。

如果 GMF 結果顯示新 PSF 重訓版在三個尺度上都不如舊版，那就確認了目前的訓練策略需要調整。如果某些尺度上新版反而更好，則說明退步可能只發生在特定條件下，可以針對性地調整。

### 目前狀態

本次重建已完成，三個尺度的 odd-frame 重建影像都已輸出到：

```
Experiments/R26NewPSFCheck/external_compare/newpsf_r26_retrain
reconstruct_progress_best_tradeoff_in_Cropped_Output_20260326_115148\
```

### 請外部 GMF 工具評分後，將結果回填到以下位置

| GMF Pitch 對應 | 回填路徑 |
|--------------|---------|
| `pitch8px`（Pitch1um_Y_100） | `Experiments/R26NewPSFCheck/external_compare/newpsf_r26_retrain/gmf_results/raw/pitch8px/GMF_score.txt` |
| `pitch0p8px`（Pitch0.1um_Y_60） | `Experiments/R26NewPSFCheck/external_compare/newpsf_r26_retrain/gmf_results/raw/pitch0p8px/GMF_score.txt` |
| `pitch0p08px`（Pitch0.01um_Y_40） | `Experiments/R26NewPSFCheck/external_compare/newpsf_r26_retrain/gmf_results/raw/pitch0p08px/GMF_score.txt` |

GMF_score.txt 回填完成後，即可使用根專案的 GMF 比較腳本，對 `newpsf_r26_retrain` 與既有 `r26_sm035` 做正式的三尺度 external compare。

---

## 10. 當前狀態與下一步

### 已完成

| 步驟 | 內容 |
|------|------|
| ✓ checkpoint 快照 | 新 PSF 重訓的 `best_tradeoff.pth.tar` 已複製到 `artifacts/newpsf_r26_retrain/weights/` |
| ✓ external recon | 三尺度 odd-frame 重建已完成（時間戳：`20260326_115148`） |
| ✓ GMF 目錄建立 | 三個 pitch 的 GMF drop-in 目錄已建立，等待回填 |
| ✓ Demo 單張比較 | 新 PSF 重訓 vs 舊 R26 的 Demo 圖對照已完成 |
| ✓ PSF formal audit | PSF 正式擬合流程審核已完成（4 項測試全通過） |
| ✓ Sandbox 脫鉤 | 本 sandbox 已成功與交付封包主結構脫鉤 |

### 待辦與下一步

| 步驟 | 內容 | 優先級 |
|------|------|--------|
| ⏳ 等待外部 GMF 結果 | 將三尺度重建丟到外部 GMF，等待 GMF_score.txt 回填 | 高 |
| ⬜ 正式 external compare | GMF 結果回來後，比較 `newpsf_r26_retrain` vs `r26_sm035` 的三尺度 GMF 分數 | 高（等 GMF 後） |
| ⬜ 決策：是否繼續追新 PSF | 根據 GMF 結果決定下一步方向 | 高（等比較後） |

### 如果要繼續追新 PSF，建議優先檢查的方向

1. **Best checkpoint 選法是否需要調整**：目前 `best_tradeoff` 的選模準則是舊 PSF 時代設計的，是否適用於新 PSF 訓練的 epoch 分布，需要重新評估。
2. **Loss 各項權重是否需要重新調整**：新 PSF 對物理層的輸出分布可能不同，現有的 `W_GRADMAG`、`W_EDGE_ORI_SIMPLE` 等權重不一定最優。
3. **Train/Val 分割是否合適**：若 val 集的特性與新 PSF 的改變方向不一致，可能導致選出的 checkpoint 在 val 上表現好但在 Demo/外部資料上退步。
4. **不要直接覆寫舊版效果的比較證據**：現有的舊版 Demo 分析與本次新 PSF 分析都應保留，作為後續調整的對照基準。

---

## 11. 相關文件索引

| 文件 | 用途說明 |
|------|---------|
| `reports/new_psf_retrain_compare_20260326.md` | 新 PSF 重訓 vs 舊版封包 R26 在 Demo 單張上的完整指標比較，含新 PSF 採用依據（SHA256 驗證）、執行方式、指標對照表與詳細解讀。**如果你想知道「新 PSF 重訓的效果好不好」，從這裡開始讀。** |
| `psf_audit/PSF_FORMAL_AUDIT_20260326.md` | PSF 正式擬合流程的完整審核記錄，逐項確認 formal entrypoint、formal_config.json、Python 測試、ValidationLab 聚合、MATLAB smoke tests 的健康狀態。**如果你想知道「PSF 擬合程式有沒有問題」，從這裡開始讀。** |
| `reports/STATUS_20260326.md` | Sandbox 整體進度的一頁摘要，包含已完成項目列表、GMF drop-in 位置、目前判讀與下一步。**快速掌握目前狀態用。** |
| `external_compare/newpsf_r26_retrain/batch_manifest.json` | 本次 external recon 的執行記錄，包含使用的 checkpoint 路徑、推論腳本路徑、三個資料集的輸入目錄、開始與完成時間。**重現實驗或追查歷史記錄時參考。** |
| `formal_newpsf_candidate/reports/NEW_PSF_FORMAL_R26_COMPARE.md` | 以 r26_sm035 完全相同 recipe、只換 PSF 的候選驗證比較摘要，形成正式 promote 的來源記錄。 |

---

> **注意事項**
>
> - 本 sandbox 內所有輸出均**不應回寫到**交付封包主結構（`Deliverables/Company_Packages/`）。
> - 若要重現本次 external recon，請確認 `C:\Users\Rio\Downloads\NTU_ImageDataset\` 下有三個資料集的 `Cropped_Output` 子目錄。
> - 使用的 Python 環境為 `C:\Users\Rio\anaconda3\python.exe`，GPU 為 NVIDIA RTX A6000（CUDA `cuda:0`）。
> - PSF 正式輸出（`PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`）**不應在本 sandbox 內被覆寫**；若需重跑 PSF fitting，應在 ValidationLab 或獨立 recheck output root 內進行。
