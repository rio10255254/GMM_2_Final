# LabSystem 逐輪必要來源與模型核對

[Lab完整沿革](<../lineage/LAB_SYSTEM.md>) · [Lab深層資料夾](<../../../LabSystem_MOSR/SOURCE_AND_MODEL_GUIDE.md>) · [目前保存狀態](<../STATUS.md>)

本次按26個Lab研究範圍逐輪核對原設定、選模說明、代表模型、必要原拍／SEM／PSF及資料清單。模型名稱相同不代表同一輪；主專案R號、Lab R號、V版本及資料stage仍分開。

## 這次具體確認

- 47個既有代表模型都有原GitHub附件位置；本機仍在的41個已用CPU開啟，模型數值可讀。另6個已清理本機副本的模型沿既有附件與原清單保存。
- 兩個R62固定輸出封裝原先沒有GitHub對應，已補回原位置；兩者與已保存V7／V28模型的模型參數完全相同，只加入固定原圖混合設定。
- 71份不可替代或固定來源全部已有提供者：25張Lab PSF原拍、39張實體棋盤／CAD原拍、R60原完整影像及量測表、兩張子像素測試原圖、Lab固定PSF與原SEM工作表。
- 508份來源、分組、執行與診斷清單都有既有保存位置；其中45份核心清單約37.5MB另放回原邏輯位置直接閱讀。
- 664個best／latest／指定輪次候選經分類；106個沒有原路徑提供者，其中36個模型狀態與已保存best／latest相同，另外70個是未採用的中途狀態，不整批上傳。

## 逐輪入口

| Lab研究 | 必要來源與代表模型 | 保留的限制 |
|---|---|---|
| [lab/BaseUNet_Baseline_20260718](<../experiments/lab__BaseUNet_Baseline_20260718.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：BaseUNet_e30 | 不同資料量／固定光學／切片與輪次版本分開；輸出報告沿用V42欄名需核對實際方法身分 |
| [lab/Modern_Restoration_Benchmarks_20260719](<../experiments/lab__Modern_Restoration_Benchmarks_20260719.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：EDSR_best、NAFNet_best | 30輪NAFNet與15輪EDSR各取最低驗證模型；同系統轉移且含固定光學轉換，不宣稱所有指標第一 |
| [lab/MOSR_BestCheckpoint_Diagnostic_20260724](<../experiments/lab__MOSR_BestCheckpoint_Diagnostic_20260724.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：V42_best_E10_EMA、V42_final_E120 | 保留共同有效母體及缺測，不以較好的一個模型覆蓋另一版 |
| [lab/MOSR_CheckpointConfig_Diagnostic_20260724](<../experiments/lab__MOSR_CheckpointConfig_Diagnostic_20260724.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：V42_best_E10_EMA、V42_final_E120 | 第10輪、120輪與定位保護各有取捨；取樣相位解釋限於已測條件 |
| [lab/R39_ShapeGeneralization](<../experiments/lab__R39_ShapeGeneralization.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：Lab_R39_best、Lab_R39_final | 與主專案R39分開，Lab起點及成像條件不能互換 |
| [lab/R40_MicroscopyFeatureCoverage](<../experiments/lab__R40_MicroscopyFeatureCoverage.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：Lab_R40_best、Lab_R40_final | 作後續角點實驗的固定Lab控制，不冒充主專案正式替代 |
| [lab/R46_CornerAwareFineTune](<../experiments/lab__R46_CornerAwareFineTune.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R46_best、R46_detail、R46_final | 25輪有效但未修好實體圓角，未採用 |
| [lab/R47_RealisticBoundaryGeneralization](<../experiments/lab__R47_RealisticBoundaryGeneralization.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R47_best、R47_detail、R47_final | 200輪仍未修好實體角點，較多訓練不等於有效 |
| [lab/R48_RealCornerTransfer](<../experiments/lab__R48_RealCornerTransfer.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R48_best、R48_detail、R48_final | 內部改善但實體更差；200輪完整負結果保留 |
| [lab/R49_CADAnchorRealGeometry](<../experiments/lab__R49_CADAnchorRealGeometry.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R49_best、R49_detail、R49_final | 100輪仍使角點退步；可靠遮罩很小，不能當全圖答案 |
| [lab/R50_PSFControlDiagnosis](<../experiments/lab__R50_PSFControlDiagnosis.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：診斷／後處理，沒有新訓練模型 | 只做診斷；完整BADS比實拍更軟，混合光學需另試 |
| [lab/R51_BlurSourceProbe](<../experiments/lab__R51_BlurSourceProbe.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R51_mixed_best、R51_mixed_final | 混合改善典型角點但大偏移比例上升，未採用 |
| [lab/R52_CornerStabilityGuard](<../experiments/lab__R52_CornerStabilityGuard.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R52_best、R52_detail、R52_final | 100輪後實體大偏移仍多，負結果與完整H歷史保留 |
| [lab/R53_RealisticDatasetCalibration](<../experiments/lab__R53_RealisticDatasetCalibration.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R53_best、R53_final | 6000組／100輪從零完成但實體角點失敗；已清理批次不重算回收 |
| [lab/R54_GeometryRootCauseProbe](<../experiments/lab__R54_GeometryRootCauseProbe.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R54_edgeband_best、R54_edgeband_final | 可靠區域內可學，但轉到實體全圖失敗；不沿此模型續訓 |
| [lab/R55_SourceStyleRealisticTraining](<../experiments/lab__R55_SourceStyleRealisticTraining.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R55_best、R55_final | best通過Lab控制角點門檻，latest退步；外部回傳另記 |
| [lab/R56_LabelCoreRepairTraining](<../experiments/lab__R56_LabelCoreRepairTraining.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R56_best、R56_final | 50輪內部改善但實體尾端更差，未採用；H備份與既有清理紀錄保留 |
| [lab/R57_GeometryConstrainedMOSR](<../experiments/lab__R57_GeometryConstrainedMOSR.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R57_asym_best、R57_asym_final | 同樣本幾何答案是訓練來源，不能當獨立SEM證據 |
| [lab/R58_MeasurementClosedLoopMOSR](<../experiments/lab__R58_MeasurementClosedLoopMOSR.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R58_full_best、R58_full_final | 答案故意只修一部分且缺實拍裁切，不能期待完全到SEM外框 |
| [lab/R59_CDClosedLoopBoundaryLayer](<../experiments/lab__R59_CDClosedLoopBoundaryLayer.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：診斷／後處理，沒有新訓練模型 | 屬同樣本後修正，數字變好不代表網路學會或獨立準確 |
| [lab/R60_SEMTruthBoundaryTraining](<../experiments/lab__R60_SEMTruthBoundaryTraining.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R60_polarity_best、R60_polarity_final | 方向與取樣修正後短測改善，完整歷史及SEM訓練依賴均保留 |
| [lab/R61_BoundaryGeneralizationUniversal](<../experiments/lab__R61_BoundaryGeneralizationUniversal.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R61_v16_best、R61_v16_final | 保留歷版；3400早期來源及舊輪廓不能單靠新推算取代 |
| [lab/R62_TargetSampleBoost](<../experiments/lab__R62_TargetSampleBoost.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：R62_v7_best、R62_v28_final | 多版模型與固定後處理分開；相位位移恢復不等於所有局部圓心更準 |
| [lab/Subpixel_Translation_Equivariance_20260720](<../experiments/lab__Subpixel_Translation_Equivariance_20260720.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：BaseUNet_e30、EDSR_best、NAFNet_best、V42_final_E120 | 插值位移不同於平台重新拍攝；MOSR未全面勝過EDSR，全部100配對與不利結果保留 |
| [lab/V41_Standalone](<../experiments/lab__V41_Standalone.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：V41_best、V41_final | 起點R61v16及11254組目標樣品／老師資料都是必要來源，不可描述為完全獨立從零 |
| [lab/V42_SoftLabelSNR](<../experiments/lab__V42_SoftLabelSNR.md>) | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；模型：V42_best_E10_EMA、V42_final_E120、V42_epoch120_wrapper | 兩輪180組煙霧結果與後來E120論文模型分開，實際E120來源須追查完整run與模型包 |

## 來源共用方式

Lab R39／R40的1,100組環形資料由Lab stage01–33資料重新組成，與前一批主專案固定環形資料不是同一套檔名或光學輸入，不重複上傳。原Lab生成器、正式BADS PSF、Gaussian控制及tra_ring_manifest直接保存；大型生成影像仍按配方重做。

R46～R56使用同一批實體棋盤／CAD原拍與逐輪生成資料；原拍只保存一次。R57～R60再使用2026-06-18的100MG完整影像與SEM參照；同樣本SEM同時參與答案及比較時，不能改稱獨立準確度。R61的3,400組繼承來源沿既有固定包，16,896組由原配方生成；R62、V41、V42再承接目標樣品、老師答案及固定模型，不能只留一個種子。

## R62兩個新補模型的身分

- `r62_v24_v7_anchor_blend10_builtin`：V7模型參數不變，輸出固定為90%原圖＋10%重建。
- `r62_v29_v28_detail35_anchor`：V28模型參數不變，使用固定detail模式、alpha0.1、sigma2.0及detail_gain0.35。

兩份原檔直接保留。另有[重建工具](../../../Tools/rebuild_r62_anchor_checkpoint.py)，由既有V7／V28模型生成相同模型參數與設定；重新儲存的檔案封裝時間及路徑會不同，不冒稱逐位元組相同。[實測紀錄](LAB_R62_REBUILD_VERIFIED_20261023.json)。

## 沒有因此上傳的內容

全部epoch快照、完整生成訓練影像、逐張重建及R61／R62所有探索模型仍不列為必要補件。R50是光學診斷，R59是同樣本後修正，本身沒有新正式訓練模型。V42的兩輪短測、完整第10輪EMA及第120輪模型分開；不以其中一份覆蓋另一份歷史。

## 按輪次取回既有模型

[47個代表模型的恢復清單](LAB_REPRESENTATIVE_MODELS_RESTORE_20261023.json.gz)沿用既有`research-results-models-20261016`附件。請搭配下載工具的`--prefix`一次選一輪或一個模型；若不指定前綴，會選到21個大型附件，並非日常閱讀或單輪重做所需。清單沒有複製模型內容，也沒有把R61／R62全部探索模型列為必要模型。

本次沒有執行訓練、推論或重新產生大型資料，也沒有清理暫存。正在訓練和論文資料保持原樣。這26輪完成的是指定來源與模型面向的核對，不能解讀成26輪都已完全重現。


## 實際GitHub取回核對

115份本批來源、說明、核心清單與兩個新補模型已從保存分支逐份取回。兩個既有R62基礎模型另從大型附件中只取出指定物件，再以取回的工具重建兩個固定輸出封裝；模型參數與輸出設定相同。47個既有代表模型所在的21個附件與原上傳核對碼一致，原附件的61,090個路徑／45,477個不同內容曾逐物件核對。沒有為了本批重複下載全部33.42GB附件。

[本批摘要](LAB_SYSTEM_DELIVERY_SUMMARY_20261023.json)／[既有模型提供者核對](LAB_EXISTING_MODEL_PROVIDERS_VERIFIED_20261023.json)／[R62遠端取回與重建](LAB_R62_REMOTE_REBUILD_VERIFIED_20261023.json)。
