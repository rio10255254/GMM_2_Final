# 訓練資料的生產方法與必要來源

可再生的大型訓練資料與中間輸出不必整套放GitHub。這裡保留原生產程式、真正設定、必要基礎來源及修正紀錄；本次沒有啟動生成、訓練或推論，也不把完整重建當成省略大檔的前提。

## 先分清楚舊固定輸入

[R33／COMBO／R39／R40的早期環形來源](../../Shared_Sources/Baseline_Ring_Inputs/README.md)並非全部都能由現存生成器證明重生。前1,000組原件另保存一次，後100組沿既有PSF處理輸入恢復；可生成的序列、形狀與顯微資料仍留原程式、設定及必要來源。[本次實測與限制](round_source_reviews/BASELINE_20261023.md)。

## 先選對資料家族

| 使用輪次 | 真正基礎資料 | 還需要保留什麼 |
|---|---|---|
| R88／R89／R90 | 各輪獨立產生，主種子880031／890041／900041 | 各輪生成器、設計與匿名光學統計；不能因同為1,280場景便混成同一資料。 |
| R91 | 自己的1,250場景，主種子910041 | 曝光檢查讀法的對照紀錄；那次沒有修改原影像，不能當作重做資料。 |
| R92 | 主種子920041，最後採用內容260ccc5b… | 原生成器，加上來源光度投影、曝光跨度修正與原接受參數。 |
| R93 | 主種子930041，最後採用內容6494719a… | 原生成器與局部修正；不是舊模板920041。後來五輪共用它。 |
| R94／R95／R96／R97／R98 | 共用R93的固定基礎來源 | 各輪讀取／在線產生觀測的程式和設定。基礎相同，不代表目標、訓練或觀測相同。 |
| R99／R100／R102／R103／R104 | 共用R92的另一套固定來源 | 各輪在線紋理、曝光、雜訊、位移或分塊規則；不可偷換成R93。 |
| Lab R61 v16 | 已有獨立生產包 | 早期繼承的3,400組來源／人工衍生幾何保留一次，其餘16,896組由原程式生成。 |
| R152論文版 | 已有獨立TIFF生產包 | 768個基礎場景、3,072視圖及原25PSF來源；不是別的專案同名R152。 |

## 從哪支程式開始

以下連結按實際原設定和程式讀取關係確認。指令只是供日後在新副本使用，本次沒有執行。原程式若把產物寫到專案內data，請在新的程式副本使用；原D工作區不因此改動。

| 輪次 | 原生產／讀取程式與設定 | 需要的上游 |
|---|---|---|
| R88_MeasurementFaithfulScratch | [generate_dataset.py](<../../Experiments/R88_MeasurementFaithfulScratch/scripts/generate_dataset.py>)、[experiment_design.json](<../../Experiments/R88_MeasurementFaithfulScratch/config/experiment_design.json>)、[execution_authorization.json](<../../Experiments/R88_MeasurementFaithfulScratch/config/execution_authorization.json>) | 獨立產生／原獨立包 |
| R89_MeasurementNativeScratch | [generate_dataset.py](<../../Experiments/R89_MeasurementNativeScratch/scripts/generate_dataset.py>)、[experiment_design.json](<../../Experiments/R89_MeasurementNativeScratch/config/experiment_design.json>)、[execution_authorization.json](<../../Experiments/R89_MeasurementNativeScratch/config/execution_authorization.json>)、[optical_statistics.json](<../../Experiments/R89_MeasurementNativeScratch/config/optical_statistics.json>) | 獨立產生／原獨立包 |
| R90_ExposureCoherentScratch | [generate_dataset.py](<../../Experiments/R90_ExposureCoherentScratch/scripts/generate_dataset.py>)、[experiment_design.json](<../../Experiments/R90_ExposureCoherentScratch/config/experiment_design.json>)、[execution_authorization.json](<../../Experiments/R90_ExposureCoherentScratch/config/execution_authorization.json>)、[optical_statistics.json](<../../Experiments/R90_ExposureCoherentScratch/config/optical_statistics.json>) | 獨立產生／原獨立包 |
| R91_DetailDecoupledScratch | [generate_dataset.py](<../../Experiments/R91_DetailDecoupledScratch/scripts/generate_dataset.py>)、[experiment_design.json](<../../Experiments/R91_DetailDecoupledScratch/config/experiment_design.json>)、[execution_authorization.json](<../../Experiments/R91_DetailDecoupledScratch/config/execution_authorization.json>)、[optical_statistics.json](<../../Experiments/R91_DetailDecoupledScratch/config/optical_statistics.json>) | 獨立產生／原獨立包 |
| R92_PhysicalTransitionBalancedScratch | [generate_dataset.py](<../../Experiments/R92_PhysicalTransitionBalancedScratch/scripts/generate_dataset.py>)、[experiment_design.json](<../../Experiments/R92_PhysicalTransitionBalancedScratch/config/experiment_design.json>)、[execution_authorization.json](<../../Experiments/R92_PhysicalTransitionBalancedScratch/config/execution_authorization.json>)、[optical_statistics.json](<../../Experiments/R92_PhysicalTransitionBalancedScratch/config/optical_statistics.json>) | 獨立產生／原獨立包 |
| R93_RecoverableDetailSeparatedScratch | [generate_dataset.py](<../../Experiments/R93_RecoverableDetailSeparatedScratch/scripts/generate_dataset.py>)、[experiment_design.json](<../../Experiments/R93_RecoverableDetailSeparatedScratch/config/experiment_design.json>)、[execution_authorization.json](<../../Experiments/R93_RecoverableDetailSeparatedScratch/config/execution_authorization.json>)、[optical_statistics.json](<../../Experiments/R93_RecoverableDetailSeparatedScratch/config/optical_statistics.json>) | 獨立產生／原獨立包 |
| R94_EvidenceConditionalScratch | [experiment_design.json](<../../Experiments/R94_EvidenceConditionalScratch/config/experiment_design.json>)、[r94_dataset.py](<../../Experiments/R94_EvidenceConditionalScratch/training/r94_dataset.py>) | r93 |
| R95_CounterfactualGateRepairScratch | [experiment_design.json](<../../Experiments/R95_CounterfactualGateRepairScratch/config/experiment_design.json>)、[r95_dataset.py](<../../Experiments/R95_CounterfactualGateRepairScratch/training/r95_dataset.py>) | r93 |
| R96_LocalizedEvidenceProtectedScratch | [experiment_design.json](<../../Experiments/R96_LocalizedEvidenceProtectedScratch/config/experiment_design.json>)、[r96_dataset.py](<../../Experiments/R96_LocalizedEvidenceProtectedScratch/training/r96_dataset.py>) | r93 |
| R97_DirectCausalPhaseScratch | [experiment_design.json](<../../Experiments/R97_DirectCausalPhaseScratch/config/experiment_design.json>)、[r97_dataset.py](<../../Experiments/R97_DirectCausalPhaseScratch/training/r97_dataset.py>) | r93 |
| R98_AggressiveTextureScratch | [experiment_design.json](<../../Experiments/R98_AggressiveTextureScratch/config/experiment_design.json>)、[r98_dataset.py](<../../Experiments/R98_AggressiveTextureScratch/training/r98_dataset.py>) | r93 |
| R99_GeometryTextureCoherentScratch | [experiment_design.json](<../../Experiments/R99_GeometryTextureCoherentScratch/config/experiment_design.json>)、[train_r99.py](<../../Experiments/R99_GeometryTextureCoherentScratch/training/train_r99.py>) | r92 |
| R100_CausalOperatorScratch | [experiment_design.json](<../../Experiments/R100_CausalOperatorScratch/config/experiment_design.json>)、[train_r100.py](<../../Experiments/R100_CausalOperatorScratch/training/train_r100.py>)、[TRAINING_DATA_REFERENCE.json](<../../Experiments/R100_CausalOperatorScratch/data/TRAINING_DATA_REFERENCE.json>) | r92 |
| R102_UniversalDetailScratch | [experiment.json](<../../Experiments/R102_UniversalDetailScratch/config/experiment.json>)、[r102_dataset.py](<../../Experiments/R102_UniversalDetailScratch/training/r102_dataset.py>)、[prepare_data.py](<../../Experiments/R102_UniversalDetailScratch/data/prepare_data.py>)、[TRAINING_DATA_REFERENCE.json](<../../Experiments/R102_UniversalDetailScratch/data/TRAINING_DATA_REFERENCE.json>) | r92 |
| R103_RecoverableDetailScratch | [experiment.json](<../../Experiments/R103_RecoverableDetailScratch/config/experiment.json>)、[r103_dataset.py](<../../Experiments/R103_RecoverableDetailScratch/training/r103_dataset.py>)、[prepare_data.py](<../../Experiments/R103_RecoverableDetailScratch/data/prepare_data.py>)、[TRAINING_DATA_REFERENCE.json](<../../Experiments/R103_RecoverableDetailScratch/data/TRAINING_DATA_REFERENCE.json>) | r92 |
| R104_PhotometricInvariantCausalGateScratch | [experiment.json](<../../Experiments/R104_PhotometricInvariantCausalGateScratch/config/experiment.json>)、[r104_dataset.py](<../../Experiments/R104_PhotometricInvariantCausalGateScratch/training/r104_dataset.py>)、[TRAINING_DATA_REFERENCE.json](<../../Experiments/R104_PhotometricInvariantCausalGateScratch/data/TRAINING_DATA_REFERENCE.json>) | r92 |
| R61_BoundaryGeneralizationUniversal | [regenerate_r61.py](<../../Deliverables/Data_Regenerators/R61_TrainingData_Regenerator_20261004/regenerate_r61.py>)、[README_TW.md](<../../Deliverables/Data_Regenerators/R61_TrainingData_Regenerator_20261004/README_TW.md>) | 獨立產生／原獨立包 |
| R152_R148v2_SafeAdaptivePSF | [generate_data.py](<../../Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004/generate_data.py>)、[R152_DATA_GENERATION_REPRODUCTION_20261004.md](<../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md>) | 獨立產生／原獨立包 |

## 原本生成後還做過什麼

R92先對69份來源觀測作整體光度投影，後來重做4組／16份曝光觀測並再投影1份；幾何與清楚目標不變，最後資料身分為260ccc5b…。這些原程式與原報告一併保留，不能只留主種子。

R93的原生成器身分與當年正式manifest相同。當年另修正11場景／44份曝光觀測，其餘1,239場景／4,956份觀測不動；清楚目標與幾何不變，最後身分為6494719a…。這是當年記錄，不保證新的環境會遇到同樣數量，也沒有為本次整理重建整套資料。

- [formal_continuous_exposure_audit_reconciliation.json](<../../Experiments/R91_DetailDecoupledScratch/reports/formal_continuous_exposure_audit_reconciliation.json>)
- [formal_recoverability_projection.json](<../../Experiments/R92_PhysicalTransitionBalancedScratch/reports/formal_recoverability_projection.json>)
- [formal_exposure_span_repair.json](<../../Experiments/R92_PhysicalTransitionBalancedScratch/reports/formal_exposure_span_repair.json>)
- [holdout_recoverability_projection.json](<../../Experiments/R92_PhysicalTransitionBalancedScratch/reports/holdout_recoverability_projection.json>)
- [holdout_exposure_span_repair.json](<../../Experiments/R92_PhysicalTransitionBalancedScratch/reports/holdout_exposure_span_repair.json>)
- [latest_repair_report.json](<../../Experiments/R93_RecoverableDetailSeparatedScratch/reports/formal_data_local_repair/latest_repair_report.json>)

R93的正式修正與封存組修正是兩支不同程式；封存組的生成／開啟規則按原設計保存，不因有生成程式就把它當作已開啟的新獨立驗證。R91原紀錄是檢查讀法修正，並無影像重生，與R92／R93上述操作分開。

## 日後要產生資料時的原入口

以R92及R93為例，原命令如下。`--full-hash-audit`是原生成程式自己要求的參數；它不是本次GitHub整理增加的省略門檻。本次只保留方法，不執行它。若程式回報某些觀測未通過，應讀原修正工具和紀錄，不能把失敗改成通過。

```powershell
python Experiments/R92_PhysicalTransitionBalancedScratch/scripts/generate_dataset.py --profile formal --full-hash-audit
python Experiments/R93_RecoverableDetailSeparatedScratch/scripts/generate_dataset.py --profile formal --full-hash-audit
```

R92原修正工具依次處理可恢復範圍與曝光跨度；R93原正式庫與封存庫各有局部修正工具。固定歷史資料仍可由既有共用來源附件另行取得，這是選項，不是閱讀方法或查看結果的必要下載。

R99至R104等原設定仍記當年的D槽基礎資料位置和固定內容身分。日後在新副本重做時，先將新副本設定的source_package或base_package指向自己產生或取回的位置。若新生成的內容身分不同，必須在新的研究設定中記錄新身分及差異，不能把它冒稱原資料，也不改寫本專案保存的歷史設定或結果。

R61與R152的獨立生產入口：

R61不是只留程式和種子就足夠：早期繼承的幾何標記曾有不同歷史版本，固定匯入的來源仍須保存。[這個小型原檔對照](r61_regeneration_example/README.md)用一組當年訓練裁切與兩版標記說明原因，不把標記版本差異當成新的物理準確度比較。

```powershell
python Deliverables/Data_Regenerators/R61_TrainingData_Regenerator_20261004/regenerate_r61.py --output-root YOUR_NEW_R61_FOLDER --report YOUR_NEW_R61_REPORT.json
python Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004/generate_data.py --workers 2 --output-dir YOUR_NEW_R152_FOLDER
```

本機2026-10-22清理後，R93的formal／locked_holdout大陣列保留在已核對的H固定封存，D只清掉重複副本；R94／95／96／97／98舊完整訓練或資料驗證前，須先依[R93取回說明](../../Experiments/R93_RecoverableDetailSeparatedScratch/data/ARCHIVE_POINTER_20261022.md)恢復同一份固定資料。生成器、原設定、修正、模型、數表及封存規則保留；不以R92替代，也不把封存組的儲存核對當成已做模型評估。

## 每輪程式、設定與來源索引

177個研究／歷史範圍各有原問題、結論限制、原報告、程式及設定位置，記在[生產與來源總表](<project_completion/curated/GENERATION_ROUTES.json.gz>)。其中18條上表路線已按實際設定確認；其餘保留原程式／報告索引，未替尚未確認的路線編造生成命令。

這次另補10份原始修正與共用來源說明，以及一份原光學頻譜來源紀錄，共11份、合計不到100KB，沒有新增訓練影像、模型或整批重建。光學頻譜的原函式、原小型輸入、顯示尺度及版本限制見[原頻譜來源與版本](<optical_calibration/SPECTRA.md>)，不把可再計算的頻譜陣列當成又一套必要大型資料。

完整原結果與失敗脈絡從[逐輪入口](<EXPERIMENTS.md>)及[完整小型結果](<project_completion/curated/FAILURE_LINEAGE_READING.md>)閱讀。2026-10-22已補回22份早期原版及R13原公式，見[找回與剩餘重做界線](KNOWN_GAPS.md)；主專案獨立R36仍未辨認。
