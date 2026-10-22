# 研究方法、完整原結果與必要來源

2026-10-22接續：[395份必要來源補件](priority_sources_20261022/README.md)，涵蓋31個R63選用模型、原拍、量測及固定驗證輸入。尚缺1個R63歷史版本，不能宣稱全專案來源已全部閉合。

目前仍有[已核實的必要來源待補](REMAINING_PRESERVATION_AUDIT_20261022.md)，全專案保存尚未完成。閱讀入口齊全與必要原件全部可取得，是兩個不同的完成條件。

2026-10-22原拍補強：[PSF100及0615來源總入口](../../Shared_Sources/PSF_Camera_Acquisitions/README.md)，包含真正完整原圖、逐張擬合對照與按需下載方法。

2026-10-22續查：[22份早期原版及R13原公式已補回](KNOWN_GAPS.md)；Lab R61內部r36與未知主R36分開，原完整結果與起點有明確取得入口。

這裡把研究閱讀和資料取得分開。先看問題、方法與結果；要生成資料或操作模型時，再取得該部分所需來源。大量訓練影像與逐張重建不必先全部下載。

## 從研究問題進入

[完整度與容量現況](COMPLETENESS_AND_CAPACITY.md)／[R128、R129、R135的重要原表與失敗](project_completion/curated/IMPORTANT_TABLES_20261022.md)。

| 目的 | 入口 |
|---|---|
| 第一次看，或換電腦後從哪裡開始 | [閱讀與取得指南](GETTING_STARTED.md) |
| R1到R153、LabSystem及歷史分支如何接起來 | [沿革](lineage/README.md)、[逐號表](lineage/ROUND_NUMBER_MAP.md) |
| 每輪問題、原方法、完整結果、失敗與後續 | [逐輪閱讀](EXPERIMENTS.md) |
| 不保留整套訓練資料時，日後如何重新生產 | [生成程式、設定與必要固定來源](GENERATION_GUIDE.md) |
| 文獻如何支持設計、官方程式用了哪版 | [文獻與原始方法](LITERATURE_GUIDE.md) |
| 哪些原拍和圖必須保留 | [來源與影像判斷](SOURCE_AND_IMAGE_DECISIONS.md)、[原圖冊](../../RECON_GALLERY.md) |
| 只取回需要的包或模型 | [附件用途與大小](ASSET_GUIDE.md)、[關鍵模型原位置](MODEL_GUIDE.md) |
| 歷史哪些部分尚缺、目前能重做到哪裡 | [缺件與限制](KNOWN_GAPS.md) |

## 按研究線深入

| 研究線 | 導讀 |
|---|---|
| 最早調參、三尺度、R12至15選模 | [早期沿革](lineage/EARLY_ROUNDS.md)、[原JSON對照](lineage/EARLY_REPORTS.md)、[方法組與固定模型](legacy_multiscale/README.md) |
| R33到COMBO、僅在舊分支的R34／35／37 | [原系列報告](../../Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md)、[分支原件](lineage/HISTORICAL_BRANCHES.md) |
| Lab校正、資料、R39／40、R46至62及V41／V42 | [Lab全線](lineage/LAB_SYSTEM.md)、[當時比較與小型重做](lab_comparisons/README.md) |
| 從零訓練與資料可學性 | [R89至93沿革](scratch_lineage/README.md)、[R93共用資料](r93_shared/README.md)、[R94／95／97／98](four_rounds/README.md) |
| 失敗後測與不利結果 | [R100／103／104完整小型原表](project_completion/curated/FAILURE_LINEAGE_READING.md) |
| 光學擬合與頻譜 | [光學保存審查](../../PSF_Fitting/docs/PSF_GITHUB_PRESERVATION_AUDIT_20261021.md)、[頻譜原來源](optical_calibration/SPECTRA.md) |
| 目前論文 | [R153原交接](../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md) |

177個現有分組的組成是122個主R資料夾、26個Lab資料夾及29個早期／歷史分組；不是177次獨立訓練。另有R34／35／37分支原件。實驗是否完成、資料是否獨立、模型是否正式採用，都回到原報告與設定。

## 保存範圍與歷史收據

[精選範圍](project_completion/SELECTIVE_DELIVERY.md)列明原程式、設定、原數表、必要來源及選圖／選模原則。[2026-10-21固定版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-curated-20261021)保留當時交付事實；目前main包含後續補查與文件整理。較早實際下載、還原、重算或執行，各保留自己的時間、固定版本及範圍，不能統稱全部歷史已重跑。

9月3日930張相機原拍與30份位置紀錄只保存一次；R61繼承影像／當時幾何、R152的25PSF、R92及R93基礎資料各有不同身分。可生成的大型產物留方法，不抹去不可替代來源。[歷次保存紀錄入口](project_completion/README.md)也分清已撤回的草稿及仍保留的正式交付。
