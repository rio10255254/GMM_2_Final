# 專案地圖

[深入各輪與交付包的內部檔案分工](<DEEP_STRUCTURE.md>)

更新：2026-10-22。這是唯一跨區域人工導航，只回答內容歸誰、先去哪裡讀；科學結論以[目前狀態](../../PROJECT_STATE.md)、[正式模型政策](../../ESTIMATOR_POLICY.json)、[實驗索引](../../Experiments/INDEX.md)及原正式報告為準。

[專案首頁](../../README.md) · [研究分區](../reproducibility/EXPERIMENTS.md) · [現在保存狀態](../reproducibility/STATUS.md)

## 依工作找入口

| 需要什麼 | 從這裡開始 |
|---|---|
| 研究沿革、同號多支線與Lab | [R1至R153及Lab](../reproducibility/lineage/README.md)、[逐號表](../reproducibility/lineage/ROUND_NUMBER_MAP.md) |
| 每輪方法、程式、完整原結果與失敗 | [逐輪閱讀](../reproducibility/EXPERIMENTS.md) |
| 文獻、資料形成與真正上游 | [文獻](../reproducibility/LITERATURE_GUIDE.md)、[資料生成](../reproducibility/GENERATION_GUIDE.md) |
| 原拍、SEM、人工與固定來源 | [共用來源](../../Shared_Sources/README.md)、[影像判斷](../reproducibility/SOURCE_AND_IMAGE_DECISIONS.md) |
| 模型、結果小包與下載大小 | [附件指南](../reproducibility/ASSET_GUIDE.md)、[模型指南](../reproducibility/MODEL_GUIDE.md) |
| 目前論文及完整圖表來源 | [R153交接](../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)、[論文證據區](../../Thesis_MOSR_Evidence/README.md) |
| 原稿、修訂與歷史 | [原稿精選](../reproducibility/project_completion/curated/draft_cleanup_20261022/README.md)、[歷史閱讀](../history/README.md) |
| 尚未尋回的歷史 | [缺件明細與已查範圍](../reproducibility/KNOWN_GAPS.md) |
| 開新實驗／維護／封存 | [操作入口](../operations/README.md)、[正式來源規則](../operations/SOURCE_OF_TRUTH_POLICY.md) |

## GitHub目前的完整根層資料夾

以下逐一對應本次實際主版本的根層資料夾；名稱保持原研究引用，每個入口都說明用途。這不是要求新建一份資料鏡像。

| 資料夾 | 放什麼 |
|---|---|
| [.github](<../../.github/README.md>) | 協作範本與檢查設定 |
| [.history](<../../.history/README.md>) | 早期編輯快照，按原時間閱讀 |
| [20260702_100MG_displacement_analysis](<../../20260702_100MG_displacement_analysis/README.md>) | 100MG樣品位移、相位配準與外部GMF |
| [20260704_20x_5x_analysis](<../../20260704_20x_5x_analysis/README.md>) | 多倍率原分析、完整數表與歷史去向 |
| [AnalysisLab](<../../AnalysisLab/README.md>) | 版本優先的可重用分析 |
| [Deliverables](<../../Deliverables/README.md>) | 獨立交付、資料生成及舊論文交接 |
| [Experiments](<../../Experiments/README.md>) | 主R系列正式實驗與報告 |
| [Historical_Archive](<../../Historical_Archive/README.md>) | 封存時的來源與狀態快照 |
| [Model](<../../Model/README.md>) | 共享主線模型、訓練與推論 |
| [PSF_Fitting](<../../PSF_Fitting/README.md>) | 光學擬合、校正與原始來源 |
| [Project_Archive](<../../Project_Archive/README.md>) | 舊根層整理的索引 |
| [Reconstruct_Progress](<../../Reconstruct_Progress/README.md>) | 舊共享重建說明 |
| [Shared_Sources](<../../Shared_Sources/README.md>) | 不可替代的共用相機、量測與固定來源入口 |
| [Step_analysis_20260623](<../../Step_analysis_20260623/README.md>) | Step樣品位移、尺寸與校正讀法 |
| [Thesis_MOSR_Evidence](<../../Thesis_MOSR_Evidence/README.md>) | 論文證據、LabSystem與原稿歷史 |
| [Tools](<../../Tools/README.md>) | 量測、治理與按需恢復 |
| [Traing_Progress](<../../Traing_Progress/README.md>) | 早期訓練、選模、未採用與失敗 |
| [Training_Data](<../../Training_Data/README.md>) | 早期共享資料生成程式 |
| [Trash_Archive](<../../Trash_Archive/README.md>) | 清理區中仍有價值的早期研究原件 |
| [Validations](<../../Validations/README.md>) | 獨立交付的原核對 |
| [_MOSR_Project_Archive_20260624](<../../_MOSR_Project_Archive_20260624/README.md>) | 6月Step／R61證據快照 |
| [_build153](<../../_build153/README.md>) | R153官方後端受阻的建置來源 |
| [_deployment_package](<../../_deployment_package/README.md>) | R26、COMBO、R39R40舊交付相容入口 |
| [_portable_env_sim_20260318](<../../_portable_env_sim_20260318/README.md>) | 舊便攜環境少量原來源 |
| [docs](<../README.md>) | 整體文件、導讀、保存及操作 |
| `LabSystem_MOSR/` | [Lab獨立研究工作區](<../../Thesis_MOSR_Evidence/LabSystem_MOSR/README.md>)；不是另一個專案根層 |

## 每輪資料夾怎麼讀

先讀`README`確認問題與完成範圍，再看正式`reports`和完整結果；需要重做才進`config/scripts`。自包含實驗另有`model/training/inference/data/runs/weights`，一輪仍由同一資料夾負責，不拆成散落全專案的第二套來源。

較早Round16至31的正式決策在`Experiments/Legacy/organized_.../roundXX/selected/reports`，R26等歷史例外依[正式來源規則](../operations/SOURCE_OF_TRUTH_POLICY.md)。`docs/evidence`是穩定引用副本，可能落後，不能覆蓋原報告。

## 新內容歸屬

| 新內容 | 唯一主人 |
|---|---|
| 一輪專用的程式、模型、數表及圖 | 該輪`Experiments`；Lab專用則留Lab原工作區 |
| 多輪共用模型程式 | `Model` |
| 多輪共用來源與生成方法 | 原`Training_Data`或`Shared_Sources`，按既有來源身分引用一次 |
| 可重用的跨版本分析 | `AnalysisLab`，維持版本優先 |
| 論文原稿、專屬證據與原圖 | `Thesis_MOSR_Evidence`，交付版進`Deliverables` |
| 光學擬合與校正 | `PSF_Fitting` |
| 新正式獨立交付 | `Deliverables`，附來源、使用及核對範圍 |
| 大量可生成產物、中途模型與歷史 | 本機／H封存；GitHub記錄方法、用途與必要來源 |

不因外觀搬動LabSystem、Model、Traing_Progress、既有日期分析或論文資料；本機原工作分支與索引保持。新原始採集未來才依[結構藍圖](../operations/PROJECT_FUTURE_STRUCTURE_PLAN.md)使用專屬入口，不追溯移動舊原拍。

## 保存與位置恢復

[封存索引](../operations/PROJECT_ARCHIVE_INDEX.md)、[已清副本的去向](../operations/D_DRIVE_FULL_CLEANUP_20261022.md)和各輪恢復入口列出原D位置與H來源。H是本機封存，不能冒稱沒有H仍可只靠GitHub精確取回所有歷史大資料。

多輪共用的9月3日930張原拍與30份平台紀錄只保存一次；R92與R93基礎、R61歷史幾何、R152的25PSF各有不同必要性。按[生成方法](../reproducibility/GENERATION_GUIDE.md)和[取得指南](../reproducibility/ASSET_GUIDE.md)選取，不重啟舊全量方案。
