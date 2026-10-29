# 歷史慣例與已知特殊狀況 / Quirks and Conventions

Last updated: 2026-04-08

這份文件記錄所有「不能改但需要知道」的歷史遺留和專案慣例。
This documents historical quirks and conventions that cannot be changed but must be understood.

---

## 1. `Traing_Progress/` 拼字錯誤

`Traing_Progress/` 少了一個 `i`（應為 `Training_Progress`）。
**不能改名**——所有訓練腳本、checkpoint 路徑、config 都硬引用這個拼錯的名稱。
改名會破壞所有現有 checkpoint 和訓練流程。

記錄於 `Model/README.md` line 52。

## 2. `Training_Data/` 被 gitignore 但有 2 個 Python 腳本被追蹤

`Training_Data/` 在 `.gitignore` line 26 被排除（訓練資料太大不進 git）。
但其中的 `Data_Simulaion.py`（注意：又一個拼字錯誤，Simulation 少了 `t`）和
`PSF_Convolution.py` 因為在 `.gitignore` 建立前就已被追蹤，所以仍在 git 裡。

這兩個腳本是資料生成流程的核心——不應移動，維持現狀。

## 3. `PSF_Fitting/bads-1.1.3/` 是 vendored MATLAB 庫

322 個檔案，佔 repo 追蹤檔案的 6%。這是 Bayesian Adaptive Direct Search 優化庫，
被 PSF 擬合 MATLAB 腳本直接引用。

不適合用 git submodule（MATLAB 工作流不支持），維持 vendored 放置。
已在 `.gitattributes` 或 GitHub 語言統計中可用 `linguist-vendored` 標記排除。

## 4. R26NewPSFCheck 的複雜目錄結構

`Experiments/R26NewPSFCheck/` 有 16 個子目錄，是專案中最複雜的實驗。
這是因為 R26 PSF 政策切換涉及多個子工作（PSF 審計、pure control、package 遷移等）。

**新實驗不需要模仿這個結構**——R33+ 的標準是 `reports/ + results/ + scripts/`。
見 `EXPERIMENT_TEMPLATE.md`。

## 5. Model/ 目錄的扁平命名

50 個 Python 檔案全部在 `Model/` 根目錄，以 `GeoEdgeAlignSR_v1_` 開頭。
功能上分為訓練、推理、實驗、分析、工具五類，但不用子目錄分隔。

這是**故意的設計**——因為：
- 所有腳本都 `import` 同一目錄下的其他腳本
- 搬進子目錄會破壞所有 `import` 路徑
- Model/README.md 已有完整的功能分類說明

## 6. 外部 GMF 比較腳本的 outlier 方法差異

| 腳本類別 | Outlier 方法 | 用途 |
|---------|------------|------|
| R26-R32 歷史腳本（FiveWay/SixWay/SevenWay） | 3-sigma | 歷史結果，不修改 |
| R33+ inline 分析 | z > 5 才移除（GMF 失敗） | 目前使用 |

詳見 `Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md`。

## 7. 量化修復（截斷 → 四捨五入）

`denormalize_to_dtype()` 在 2026-04-08 從 `.astype(dtype)` 截斷改為 `np.rint()` 四捨五入。
已修復的腳本：
- `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`
- `Model/GeoEdgeAlignSR_v1_Infer_TTA.py`
- `Deliverables/Company_Packages/.../Infer_v5...SimpleTest.py`
- `Experiments/R26NewPSFCheck/.../Infer_v5...SimpleTest.py`（2 份）

詳見 `Experiments/R33RobustLoss/reports/QUANTIZATION_FIX_ANALYSIS.md`。

## 8. Sequence Analysis 角度取樣

2026-04-08 從 360 改為 720 角度（降低 circle-fit 噪聲地板 29%）。
只影響 `run_sequence_analysis.py` 的 `extract_radial_edge_candidates` 呼叫。
`run_single_image_analysis.py` 仍用 360（單張分析不需要更高精度）。
Hotspot persistence 仍用 360-bin heatmap。

## 9. 合成訓練資料的 PSF 版本

| 資料 | PSF 版本 | 日期 |
|------|---------|------|
| `tra_src_ring/` | 2025 年舊版（未知精確版本） | 2025-12 |
| `generated_convolved/stage_19-28/` | 新 Whole-FOV PSF | 2026-04-06 重新卷積 |
| Model physics layer | 新 Whole-FOV PSF | 2026-03-25 |

tra_src_ring 的 PSF 不一致從 R30 就存在，不影響已驗證結果。
詳見 `Experiments/R38v2SeqFixed/reports/DATA_FLOW_AUDIT.md`。
