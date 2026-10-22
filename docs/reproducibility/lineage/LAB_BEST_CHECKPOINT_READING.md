# Lab最佳模型診斷：原數表應如何閱讀

2026-10-22整理原2026-07-24輸出。原診斷資料夾只有manifest與CSV，沒有原文字報告；本頁補閱讀說明，原表和原研究判決不改。

## 只換甚麼

[原診斷設定](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation_manifest_best_checkpoint.json)明記：只把MOSR第120輪換成訓練選中的第10輪；Raw、Base U-Net、EDSR及NAFNet保持各自原來源。這裡的MOSR屬舊V42研究，不是後來R152。

每個序列仍使用Raw移動品質預先鎖定的30個相鄰步，柱／孔共用各自原九顆參照與校準。不能為某個模型事後挑更好的影格。

## 缺測與共同母體

[原可用性表](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation/displacement_availability.csv)顯示：柱的20x／0.5um序列，EDSR只有28個可評估步，其餘原選30步。主比較使用所有方法共同有效的交集，因此四序列合併後柱為118步、孔120步，不把缺兩步補成零。

[逐步原量測](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation/displacement_step_measurements.csv)、[各序列完整原表](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation/displacement_summary.csv)與[合併共同母體原表](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation/displacement_pooled_common_valid.csv)都保留，不能只留下較好的一格。

## 原表實際說了甚麼

下表只是原合併表`mae_nm`欄的三位小數顯示，原完整精度以上方CSV為準。

| 方法 | 柱 MAE nm，n=118 | 孔 MAE nm，n=120 |
|---|---:|---:|
| Raw | 9.297 | 7.315 |
| Base U-Net | 5.916 | 6.148 |
| EDSR | 6.141 | 5.990 |
| NAFNet | 10.587 | 6.897 |
| MOSR第10輪 | 6.412 | 6.706 |

第10輪MOSR在這份表較Raw改善，仍未在柱／孔的這項讀值都勝過EDSR或Base U-Net。不能把換最佳模型後的改善延伸成各形貌、尺寸、速度或獨立準確度都最好。

四序列混有不同名義步長，直接把合併後`signed_step_sd_nm`當作同一步長的不確定度會混入步長本身的差異。應回到每序列原表，或讀已逐步扣除各自名義參照的誤差欄；PI命令是原實驗位置參照，不因此變成獨立絕對真值。

第120輪的原比較與[另一組設定診斷](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_CheckpointConfig_Diagnostic_20260724/diagnosis/DIAGNOSTIC_REPORT_zh-TW.md)仍保留。[V41到V42的真正來源與完整訓練](../lab_comparisons/V42_HISTORY.md)另分清兩輪短測、完整120輪、平滑best第10輪與末檔。

本頁沒有重新推論、重跑量測、重選影格或改變論文採用模型。
