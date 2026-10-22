# MOSR：顯微影像重建與位移量測

[深入實驗、Lab與交付包的內部資料夾](<docs/navigation/DEEP_STRUCTURE.md>)

這項研究比較影像重建如何改變輪廓、尺寸、位移穩定性與運算時間。影像變清楚不一定代表量測更準；成功、代價與失敗都保留在各輪原報告。

**目前論文採用 R152／RAW；原正式基準仍是 COMBO。** [目前論文交接與完整比較](Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)說明採用理由與限制，[研究現況](PROJECT_STATE.md)保留正式判決。

## 從這六個入口開始

| 想了解什麼 | 從這裡讀 |
|---|---|
| 研究為什麼走到現在這個方法 | [研究沿革：早期、主線與 LabSystem](docs/reproducibility/lineage/README.md) |
| 某一輪做了什麼、結果如何 | [按階段與輪次閱讀](docs/reproducibility/EXPERIMENTS.md) |
| 原拍、量測、模型在哪裡 | [共用來源](Shared_Sources/README.md) → [按用途取得檔案](docs/reproducibility/ASSET_GUIDE.md) |
| 沒有大型訓練資料，如何重做 | [生成方法與必要來源](docs/reproducibility/GENERATION_GUIDE.md) |
| 文獻、原方法與官方程式 | [文獻及方法依據](docs/reproducibility/LITERATURE_GUIDE.md) |
| 已保存哪些、還缺什麼 | [目前保存狀態](docs/reproducibility/STATUS.md) |

第一次閱讀可跟著[入門路線](docs/reproducibility/GETTING_STARTED.md)，不用先下載模型或整套影像。

## 資料夾的角色

```text
GMM_2_Final/
├── Experiments/             主專案各輪：原報告、程式、設定與結果
├── Thesis_MOSR_Evidence/     論文證據、LabSystem研究及原稿歷史
├── Shared_Sources/          共用原拍、平台紀錄、SEM與固定來源入口
├── PSF_Fitting/             光學校正、原擬合與分析
├── Model/、Training_Data/   共用模型與資料生成程式
├── AnalysisLab/             跨版本量測與分析
├── Deliverables/            獨立使用包與原交付
├── Traing_Progress/         早期選模、訓練及失敗歷史
└── docs/                    閱讀路線、文獻、來源、保存與維護說明
```

這是閱讀用的主要分區；其餘日期資料夾與歷史區可在[完整專案地圖](docs/navigation/PROJECT_MAP.md)找到。原實驗檔案維持既有位置，讓原程式、原報告與論文引用仍能對得上。

## 保存到哪裡

主要脈絡、程式、設定、原結果與重要來源已整理；**逐輪必要來源仍在補查，尚未確認全專案沒有遺漏。** 已知 R63 缺一個原選中模型，主專案 R36 尚未辨認。最新補件與影響集中在[目前狀態](docs/reproducibility/STATUS.md)，歷次收據另見[保存歷史](docs/reproducibility/project_completion/README.md)。

不可替代的原拍與量測按來源保存一次；可再生成的大型訓練資料和整批重建，保存生成方法、設定及必要輸入。GitHub附件按需下載，沒有要求先取回全部資料。

要維護研究，請讀[操作入口](docs/operations/README.md)及[正式來源規則](docs/operations/SOURCE_OF_TRUTH_POLICY.md)。
