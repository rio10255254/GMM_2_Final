# 主R141起：光學配對與論文比較

[全部分區](../EXPERIMENTS.md) · [研究沿革](../lineage/README.md) · [目前保存狀態](../STATUS.md)

部署設計、短測與正式完成分開；目前論文交接在R153。

以下是閱讀順序，不表示相鄰兩輪必然繼承同一模型或資料。原正式報告優先於卡片的早期摘要。

| 實驗 | 研究問題 | 判讀與限制 |
|---|---|---|
| [main/R141_PSF25_AdaptiveTop4_Standalone](../experiments/main__R141_PSF25_AdaptiveTop4_Standalone.md) | 逐張從25顆光學候選選四顆 | 衍生自R140v2的可推論包，非已完成新長訓練與930驗收 |
| [main/R142_PSF100_AdaptiveTop8_Standalone](../experiments/main__R142_PSF100_AdaptiveTop8_Standalone.md) | 擴為100顆並逐張選八顆 | 指定實測100顆未安裝；推論拒絕是正確行為，合成測試不冒充實測 |
| [main/R143_PSF25_MatchedPairs](../experiments/main__R143_PSF25_MatchedPairs.md) | 以模型同一25PSF形成訓練配對 | 尺寸參照差較小但位移／重拍退步；PSF選擇不成功 |
| [main/R144_Center9PSF25_MatchedPairs](../experiments/main__R144_Center9PSF25_MatchedPairs.md) | 更換中心九顆擬合的25PSF | 方向對應錯誤，160次中止；不能與R145修正後完整結果混用 |
| [main/R145_Center9PSF25_CorrectedPairs](../experiments/main__R145_Center9PSF25_CorrectedPairs.md) | 修正方向後完整測試新PSF | 位移／輪廓較R143改善但尺寸仍偏；同九顆SEM只屬校準同樣本比較 |
| [main/R146_SEMCoreHaloPSF25_MatchedPairs](../experiments/main__R146_SEMCoreHaloPSF25_MatchedPairs.md) | 把真實SEM外框形成的中心淡尾PSF用於模型 | 較能預測照片不等於重建量測更好；多數短步與輪廓退步 |
| [main/R147_FullResPSFConsistency](../experiments/main__R147_FullResPSFConsistency.md) | 修復資料與模型內PSF的尺度用法 | 尺寸重拍改善但短步退步；後續脈絡／邊界分工需另驗證 |
| [main/R148_MeasurementStableNativePSF](../experiments/main__R148_MeasurementStableNativePSF.md) | 把決定邊界的主幹全部留在原尺寸 | 正式只留下62次且無保存點；累積依賴超出訓練邊界，不續跑 |
| [main/R148v2_HybridContextNativePSF](../experiments/main__R148v2_HybridContextNativePSF.md) | 一次多尺度脈絡加三段受控原尺寸邊界 | 8192與930完成；尺寸重拍佳但尺寸偏差仍在，是R152基底 |
| [main/R149_MatchedGeometryLocalBoundary](../experiments/main__R149_MatchedGeometryLocalBoundary.md) | 補接近實拍尺度的程序排列與局部邊界要求 | 兩版短測都未達3%門檻，不開正式長訓練 |
| [main/R150_MatchedGeometryMeanPSF](../experiments/main__R150_MatchedGeometryMeanPSF.md) | 保持架構，測新排列與訓練推論共用平均PSF | 短步與去尺寸形狀小改善，直徑重拍／輪廓／SEM退步；兩因素仍未分離 |
| [main/R151_R148v2_AdaptivePSFFusion](../experiments/main__R151_R148v2_AdaptivePSFFusion.md) | 恢復可參與學習的光學加權融合 | 機制可運作但現有25顆不能可靠辨識，未開始正式8192 |
| [main/R152_R148v2_SafeAdaptivePSF](../experiments/main__R152_R148v2_SafeAdaptivePSF.md) | 保存R148v2效益並加入有作用的論文光學模組 | 8192擴充與930完成；位移／重拍收益保留，尺寸偏大與較慢成本不可省略 |
| [main/R153_MeanExternalBenchmark](../experiments/main__R153_MeanExternalBenchmark.md) | 用九顆平均位移與外部架構完成論文比較 | 十方法930張／30趟完成，兩官方後端受阻；各自訓練目標與不等輪數如實保留 |
