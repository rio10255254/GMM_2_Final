# LabSystem：校正、資料與專屬模型

[全部分區](../EXPERIMENTS.md) · [研究沿革](../lineage/README.md) · [目前保存狀態](../STATUS.md)

包括Lab各輪與V41／V42；Lab R61內部r36不是主專案R36。

以下是閱讀順序，不表示相鄰兩輪必然繼承同一模型或資料。原正式報告優先於卡片的早期摘要。

| 實驗 | 研究問題 | 判讀與限制 |
|---|---|---|
| [lab/BaseUNet_Baseline_20260718](../experiments/lab__BaseUNet_Baseline_20260718.md) | 以基礎U-Net作參數與訓練資料受控比較 | 不同資料量／固定光學／切片與輪次版本分開；輸出報告沿用V42欄名需核對實際方法身分 |
| [lab/Modern_Restoration_Benchmarks_20260719](../experiments/lab__Modern_Restoration_Benchmarks_20260719.md) | 比較柱、孔、線三形貌的EDSR／NAFNet等方法 | 30輪NAFNet與15輪EDSR各取最低驗證模型；同系統轉移且含固定光學轉換，不宣稱所有指標第一 |
| [lab/MOSR_BestCheckpoint_Diagnostic_20260724](../experiments/lab__MOSR_BestCheckpoint_Diagnostic_20260724.md) | 檢查最佳保存模型與最後模型對位移結果的影響 | 保留共同有效母體及缺測，不以較好的一個模型覆蓋另一版 |
| [lab/MOSR_CheckpointConfig_Diagnostic_20260724](../experiments/lab__MOSR_CheckpointConfig_Diagnostic_20260724.md) | 拆解EDSR與MOSR位移差異的來源 | 第10輪、120輪與定位保護各有取捨；取樣相位解釋限於已測條件 |
| [lab/R39_ShapeGeneralization](../experiments/lab__R39_ShapeGeneralization.md) | Lab環境中的多形狀轉移 | 與主專案R39分開，Lab起點及成像條件不能互換 |
| [lab/R40_MicroscopyFeatureCoverage](../experiments/lab__R40_MicroscopyFeatureCoverage.md) | Lab環境中的顯微特徵對照 | 作後續角點實驗的固定Lab控制，不冒充主專案正式替代 |
| [lab/R46_CornerAwareFineTune](../experiments/lab__R46_CornerAwareFineTune.md) | 以角點資料保守修正Lab模型 | 25輪有效但未修好實體圓角，未採用 |
| [lab/R47_RealisticBoundaryGeneralization](../experiments/lab__R47_RealisticBoundaryGeneralization.md) | 增加較真實的邊界與背景 | 200輪仍未修好實體角點，較多訓練不等於有效 |
| [lab/R48_RealCornerTransfer](../experiments/lab__R48_RealCornerTransfer.md) | 用實體失敗型態與幾何標記改善角點 | 內部改善但實體更差；200輪完整負結果保留 |
| [lab/R49_CADAnchorRealGeometry](../experiments/lab__R49_CADAnchorRealGeometry.md) | 加入可靠區域內的實體CAD答案 | 100輪仍使角點退步；可靠遮罩很小，不能當全圖答案 |
| [lab/R50_PSFControlDiagnosis](../experiments/lab__R50_PSFControlDiagnosis.md) | 診斷Lab光學模糊是否過強 | 只做診斷；完整BADS比實拍更軟，混合光學需另試 |
| [lab/R51_BlurSourceProbe](../experiments/lab__R51_BlurSourceProbe.md) | 短測高斯、弱BADS與混合光學 | 混合改善典型角點但大偏移比例上升，未採用 |
| [lab/R52_CornerStabilityGuard](../experiments/lab__R52_CornerStabilityGuard.md) | 續接混合光學並加入角點穩定限制 | 100輪後實體大偏移仍多，負結果與完整H歷史保留 |
| [lab/R53_RealisticDatasetCalibration](../experiments/lab__R53_RealisticDatasetCalibration.md) | 重新平衡環形、形狀、顯微、背景與CAD資料 | 6000組／100輪從零完成但實體角點失敗；已清理批次不重算回收 |
| [lab/R54_GeometryRootCauseProbe](../experiments/lab__R54_GeometryRootCauseProbe.md) | 拆解重建造成角點損害及局部CAD可學性 | 可靠區域內可學，但轉到實體全圖失敗；不沿此模型續訓 |
| [lab/R55_SourceStyleRealisticTraining](../experiments/lab__R55_SourceStyleRealisticTraining.md) | 保留來源亮暗風格修復假高對比答案 | best通過Lab控制角點門檻，latest退步；外部回傳另記 |
| [lab/R56_LabelCoreRepairTraining](../experiments/lab__R56_LabelCoreRepairTraining.md) | 只修復弱答案核心區域 | 50輪內部改善但實體尾端更差，未採用；H備份與既有清理紀錄保留 |
| [lab/R57_GeometryConstrainedMOSR](../experiments/lab__R57_GeometryConstrainedMOSR.md) | 加入實體SEM半徑約束尺寸 | 同樣本幾何答案是訓練來源，不能當獨立SEM證據 |
| [lab/R58_MeasurementClosedLoopMOSR](../experiments/lab__R58_MeasurementClosedLoopMOSR.md) | 使用部分SEM修正答案做閉環試驗 | 答案故意只修一部分且缺實拍裁切，不能期待完全到SEM外框 |
| [lab/R59_CDClosedLoopBoundaryLayer](../experiments/lab__R59_CDClosedLoopBoundaryLayer.md) | 在同一影像上估計尺寸再移動邊界 | 屬同樣本後修正，數字變好不代表網路學會或獨立準確 |
| [lab/R60_SEMTruthBoundaryTraining](../experiments/lab__R60_SEMTruthBoundaryTraining.md) | 修復實拍裁切答案、亮暗方向與真值權重 | 方向與取樣修正後短測改善，完整歷史及SEM訓練依賴均保留 |
| [lab/R61_BoundaryGeneralizationUniversal](../experiments/lab__R61_BoundaryGeneralizationUniversal.md) | 加入通用邊界、位移及Step保護形成v16 | 保留歷版；3400早期來源及舊輪廓不能單靠新推算取代 |
| [lab/R62_TargetSampleBoost](../experiments/lab__R62_TargetSampleBoost.md) | 實體目標增補與保守原圖參考輸出 | 多版模型與固定後處理分開；相位位移恢復不等於所有局部圓心更準 |
| [lab/Subpixel_Translation_Equivariance_20260720](../experiments/lab__Subpixel_Translation_Equivariance_20260720.md) | 對真實結構施加已知數學位移作壓力測試 | 插值位移不同於平台重新拍攝；MOSR未全面勝過EDSR，全部100配對與不利結果保留 |
| [lab/V41_Standalone](../experiments/lab__V41_Standalone.md) | 把目標樣品探索鏈整理成兩階段訓練 | 起點R61v16及11254組目標樣品／老師資料都是必要來源，不可描述為完全獨立從零 |
| [lab/V42_SoftLabelSNR](../experiments/lab__V42_SoftLabelSNR.md) | 柔化邊界答案並加入影像品質閘 | 兩輪180組煙霧結果與後來E120論文模型分開，實際E120來源須追查完整run與模型包 |
