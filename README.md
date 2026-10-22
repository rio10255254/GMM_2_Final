# GMM_2_Final：顯微重建與位移量測研究

這裡保存顯微影像重建的研究：如何形成訓練資料、模型如何改變邊界與位移，以及實際量測有哪些收益、代價與失敗。看起來清楚、尺寸正確、位移穩定和速度快，是不同問題，不能用一個分數代替。

目前論文採用 **R152／RAW**；[R153論文交接與十方法完整結果](Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)是現在的閱讀起點。**COMBO**仍是原正式基準，其他模型保持各自的研究身分。最新判決以[專案狀態](PROJECT_STATE.md)、[正式模型政策](ESTIMATOR_POLICY.json)及各輪原報告為準。

## 依你的目的開始

| 要做什麼 | 第一個入口 |
|---|---|
| 第一次來，先看研究內容與下載界線 | [閱讀與取得指南](docs/reproducibility/GETTING_STARTED.md) |
| 從R1到R153理解前後關係，包含LabSystem | [研究沿革](docs/reproducibility/lineage/README.md)、[逐號查找](docs/reproducibility/lineage/ROUND_NUMBER_MAP.md) |
| 找某一輪的問題、方法、原程式、結果與失敗 | [逐輪閱讀入口](docs/reproducibility/EXPERIMENTS.md)、[正式實驗索引](Experiments/INDEX.md) |
| 重新生產訓練資料 | [生成方法、設定與必要來源](docs/reproducibility/GENERATION_GUIDE.md) |
| 找文獻、設計依據與官方原碼 | [文獻與固定來源](docs/reproducibility/LITERATURE_GUIDE.md) |
| 找完整原數表與重要圖片 | [原結果及失敗](docs/reproducibility/project_completion/curated/FAILURE_LINEAGE_READING.md)、[圖冊](RECON_GALLERY.md) |
| 取得原拍、選用模型或小型結果包 | [按用途取得附件](docs/reproducibility/ASSET_GUIDE.md)、[關鍵模型與來源](docs/reproducibility/MODEL_GUIDE.md) |
| 看所有資料夾各放什麼 | [完整專案地圖](docs/navigation/PROJECT_MAP.md) |

## 檔案怎麼分

```text
GMM_2_Final/
├── README.md                      這份總入口
├── PROJECT_STATE.md               最新研究現況
├── ESTIMATOR_POLICY.json          正式模型身分
├── docs/                          閱讀指南、沿革、文獻、保存與操作說明
├── Experiments/                   主專案各輪的程式、設定、正式報告和結果
├── Thesis_MOSR_Evidence/           論文證據、LabSystem及早期論文歷史
├── Model/                         共享主線模型、訓練及推論程式
├── Training_Data/                 共享資料生成程式
├── Shared_Sources/                不可替代原始來源的說明與取得入口
├── PSF_Fitting/                   光學校正、擬合與原始來源
├── AnalysisLab/                   跨版本分析方法
├── Deliverables/                  獨立交付與資料生產包
├── Validations/                   各交付包當時的核對記錄
├── Tools/                         操作、分析及選取恢復工具
├── Traing_Progress/                早期訓練、選模及失敗歷史
└── 其餘日期／封存資料夾            舊樣品分析、交付與歷史來源；見專案地圖
```

各主要資料夾都附入口說明。研究原有位置保持穩定，避免改斷當時的程式與來源引用；LabSystem仍在論文證據區內。同號R、資料stage及V版本要分開讀，不能當成同一輪。

## GitHub保留到哪裡

原程式、設定、文獻與設計說明、完整量測及比較表、失敗原因、少量有用途的原圖與關鍵模型，是保存重點。大量可再生的訓練影像、逐張重建及中間陣列，保留生產方法和必要來源，不再整套上傳。

2026年9月3日的 **930張相機原拍與30份平台原始紀錄**是多輪共用來源，已保存一次；它們不是模型重建影像。歷史正式附件仍可按需要取用，首頁不要求先下載全部大檔。

[2026-10-21精選固定版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-curated-20261021)保留當次實際交付範圍；目前`main`另含後續沿革與文件整理。六份超量舊草稿已先保留有價值內容再撤下，[處理紀錄](docs/reproducibility/project_completion/curated/draft_cleanup_20261022/README.md)另存，不是目前待上傳清單。

## 尚未找回的歷史

R94／R95尚有22份較早程式或設定版本未尋回；早期R13有9項總分缺少當時公式；R36編號尚未找到足以指定的獨立證據。[缺件明細與已查範圍](docs/reproducibility/KNOWN_GAPS.md)區分哪些原件仍在、哪些不能精確重做。沒有把未寫出的量補造，也沒有重跑全部歷史訓練。

維護研究時，先讀[目前狀態](PROJECT_STATE.md)及[正式來源規則](docs/operations/SOURCE_OF_TRUTH_POLICY.md)。2026-10-22這次整理只補閱讀入口、來源界線和文件，不改科學結論、原模型、論文、訓練資料或D槽工作版本。[文件調整與舊版位置](docs/history/README.md)可查原說明。
