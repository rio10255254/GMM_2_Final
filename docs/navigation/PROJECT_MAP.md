# 專案地圖

[專案首頁](../../README.md) · [文件地圖](../README.md) · [深層檔案導讀](DEEP_STRUCTURE.md)

更新：2026-10-24。回答「這個資料夾放什麼、我該去哪」。科學結論以 [PROJECT_STATE.md](../../PROJECT_STATE.md)、[ESTIMATOR_POLICY.json](../../ESTIMATOR_POLICY.json)、[Experiments/INDEX.md](../../Experiments/INDEX.md) 與各輪正式報告為準。

## 按用途找

| 我想… | 打開 |
|---|---|
| 知道現在用哪個模型、結果如何 | [PROJECT_STATE.md](../../PROJECT_STATE.md) |
| 看某一輪做了什麼 | `Experiments/R##_…/README.md` 與 `reports/`；清單 [INDEX.md](../../Experiments/INDEX.md)；階段式 [EXPERIMENTS.md](../reproducibility/EXPERIMENTS.md)；逐號 [ROUND_NUMBER_MAP](../reproducibility/lineage/ROUND_NUMBER_MAP.md) |
| 改論文 | [R153 論文交接](../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)、[論文證據區](../../Thesis_MOSR_Evidence/README.md) |
| 找原始照片、SEM、平台紀錄 | [Shared_Sources](../../Shared_Sources/README.md) → [按用途取得](../reproducibility/ASSET_GUIDE.md) |
| 找光學校正 | [PSF_Fitting](../../PSF_Fitting/README.md) |
| 跑訓練／推論 | 第一代 [Model](../../Model/README.md)；第二代在各輪或 [Deliverables/R152_*](../../Deliverables/README.md) |
| 找 Lab 系統那條線 | [LabSystem_MOSR](../../Thesis_MOSR_Evidence/LabSystem_MOSR/README.md)、[Lab 全線](../reproducibility/lineage/LAB_SYSTEM.md) |
| 生成訓練資料 | [GENERATION_GUIDE](../reproducibility/GENERATION_GUIDE.md)（**每輪來源不同**） |
| 讀文獻 | [LITERATURE_GUIDE](../reproducibility/LITERATURE_GUIDE.md) |
| 查缺件 | [KNOWN_GAPS](../reproducibility/KNOWN_GAPS.md) |
| 開新實驗／維護 | [operations/README](../operations/README.md) |

## 根目錄資料夾

### 日常會用

| 資料夾 | 內容 |
|---|---|
| [Experiments](../../Experiments/README.md)（~14,800 檔） | 主專案各輪（R26–R153）：`README.md`、`scripts/`、`reports/`、`results/`，新近輪次另有 `model/`、`runs/`、`weights/` |
| [Model](../../Model/README.md) | 第一代共用模型、訓練、推論、外部 GMF 比較、自動調參；`tests/` 有推論測試 |
| [PSF_Fitting](../../PSF_Fitting/README.md) | MATLAB 擬合 PSF（Zernike + BADS）與 Wiener 反捲積驗證 |
| [Shared_Sources](../../Shared_Sources/README.md) | **不可替代的原始資料入口**：930 張位移重拍、PSF 原拍、SEM、固定參照 |
| [Thesis_MOSR_Evidence](../../Thesis_MOSR_Evidence/README.md)（~3,000 檔） | 論文證據；含 `LabSystem_MOSR/` 與跨模型比較報告 |
| [Tools](../../Tools/README.md) | 控制中心、驗證器、取回／還原／核對工具、位移演算法 |
| [docs](../README.md) | 說明文件 |

### 交付與分析

| 資料夾 | 內容 |
|---|---|
| [Deliverables](../../Deliverables/README.md) | 可獨立使用的包：R152 獨立版／影像版、R61 訓練資料重新生成器、R128–R130 論文交接包、ONNX 包 |
| [_deployment_package](../../_deployment_package/README.md) | COMBO、R26、R39R40 較早的正式交付（保留當時介面） |
| [Validations](../../Validations/README.md) | 交付包當時的核對 |
| [AnalysisLab](../../AnalysisLab/README.md) | 跨版本幾何品質分析 |
| [Training_Data](../../Training_Data/README.md) | 第一代資料生成程式（影像被 gitignore） |

### 依樣品／日期分的分析（不要混用）

| 資料夾 | 內容 |
|---|---|
| [20260702_100MG_displacement_analysis](../../20260702_100MG_displacement_analysis/README.md) | 100MG 樣品 X 方向位移（不是 Step，也不是 9/3 的 30 趟） |
| [20260704_20x_5x_analysis](../../20260704_20x_5x_analysis/README.md) | 20×／5× 實拍、重建與比較 |
| [Step_analysis_20260623](../../Step_analysis_20260623/README.md) | Step 樣品的位移、尺寸、形狀 |
| [_MOSR_Project_Archive_20260624](../../_MOSR_Project_Archive_20260624/README.md) | 6 月 Step／R61 證據快照（**不是**最新入口） |

### 歷史與封存（通常不必打開）

| 資料夾 | 內容 |
|---|---|
| [Traing_Progress](../../Traing_Progress/README.md) | 早期訓練、選模、失敗（**拼字是歷史，勿改名**） |
| [Reconstruct_Progress](../../Reconstruct_Progress/README.md) | 舊共享重建說明 |
| [Historical_Archive](../../Historical_Archive/README.md)、[Project_Archive](../../Project_Archive/README.md)、[Trash_Archive](../../Trash_Archive/README.md) | 各時期封存；Trash_Archive 內仍有早期 R2／3／6／7／9 的調參原件 |
| [_build153](../../_build153/README.md) | R153 官方 Mamba 後端建置失敗的來源 |
| [_portable_env_sim_20260318](../../_portable_env_sim_20260318/README.md) | 舊便攜環境少量原始碼 |
| `.history/`、`.github/` | 編輯器歷史快照；協作範本與檢查 |

## 每輪實驗資料夾

```text
Experiments/R##_Description/
├── README.md     問題與結果摘要
├── MANIFEST.md   完成後的檔案清單
├── scripts/      該輪專用程式
├── reports/      R##_RESULTS／SUMMARY／AUDIT／METHODOLOGY.md（正式報告，只在此編輯）
└── results/      數字表、圖、外部 GMF 輸出
```

先讀 `README` 確認問題與完成範圍，再看 `reports` 與完整結果；要重做才進 `scripts` 與設定。命名 `R##[v#]_PascalCase`，歷史例外 `R26NewPSFCheck`、`R32Sandbox`、`R33RobustLoss`。較早 Round16–31 的正式決策在 `Traing_Progress/organized_…/roundXX/selected/reports`（見 [LEGACY_ROUNDS_OPERATIONS](../operations/LEGACY_ROUNDS_OPERATIONS.md)）。

## 新內容歸誰

| 新內容 | 唯一的家 |
|---|---|
| 一輪專用的程式、模型、數表、圖 | 該輪 `Experiments/R##…`（Lab 專用留 Lab 工作區） |
| 多輪共用模型程式 | `Model` |
| 多輪共用原始來源與生成方法 | `Training_Data`、`Shared_Sources`（引用一次） |
| 跨版本分析工具 | `AnalysisLab` |
| 論文原稿與專屬證據 | `Thesis_MOSR_Evidence`；交付版進 `Deliverables` |
| 光學擬合 | `PSF_Fitting` |
| 大量可生成產物、中途模型 | 本機／H 槽；GitHub 只記方法、用途與必要來源 |

不為了外觀搬動 LabSystem、Model、Traing_Progress、既有日期分析或論文資料，因為原程式與報告引用這些路徑。

## 保存與位置恢復

[封存索引](../operations/PROJECT_ARCHIVE_INDEX.md)、[已清副本的去向](../operations/D_DRIVE_FULL_CLEANUP_20261022.md)與各輪恢復入口列出原 D 位置與 H 來源。H 是本機封存，不能宣稱沒有 H 仍可只靠 GitHub 精確取回所有歷史大資料。多輪共用的 930 張原拍與 30 份平台紀錄只保存一次；R92／R93 基礎、R61 歷史幾何、R152 的 25 PSF 各有必要性，按 [取得指南](../reproducibility/ASSET_GUIDE.md) 選取。

> 本頁 2026-10-24 改寫前的原文逐位元組保留在 [docs__navigation__PROJECT_MAP.md](../history/BEFORE_PLAIN_REWRITE_20261024/docs__navigation__PROJECT_MAP.md)。
