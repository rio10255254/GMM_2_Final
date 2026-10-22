# lab/MOSR_BestCheckpoint_Diagnostic_20260724 研究與重做紀錄

檢查最佳保存模型與最後模型對位移結果的影響

保留共同有效母體及缺測，不以較好的一個模型覆蓋另一版

## 必要來源

唯一改動是以訓練選中第10輪替換MOSR第120輪；保留原manifest、Raw鎖定每序列30相鄰步、九顆參照設定、可用性與共同有效母體四張CSV。柱的共同母體118、孔120；不能把缺兩步默默補值。

## 影像保存理由

本輪首要證據是原四張CSV與可用性；任何例圖須沿同一Raw鎖定母體及第10輪來源，不能讓缺測或漂亮單圖取代完整結果。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

本輪當年沒有文字報告，原件是設定與完整數表：

- [原第10輪替換設定](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation_manifest_best_checkpoint.json)
- [原可用性與缺測表](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation/displacement_availability.csv)
- [逐步原量測](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation/displacement_step_measurements.csv)
- [各序列完整原表](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation/displacement_summary.csv)
- [共同有效母體完整原表](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_BestCheckpoint_Diagnostic_20260724/evaluation/displacement_pooled_common_valid.csv)
- [後補讀法與結果限制](../lineage/LAB_BEST_CHECKPOINT_READING.md)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。

## 2026-10-22：這一輪在整條研究中的位置

[按R1至R153查找](../lineage/ROUND_NUMBER_MAP.md)／[本研究線的來源、得失與後續](../lineage/LAB_SYSTEM.md)。本輪上方已改為具體必要來源；原日期的保存、失敗與執行證據保留各自範圍，不以文件數或標號連續性冒稱全部歷史已重現。

## 原表的直接閱讀說明

[第10輪替換、118／120步共同母體、缺測與五方法完整結果](../lineage/LAB_BEST_CHECKPOINT_READING.md)。原資料夾當年沒有文字報告；此處補導讀，不改原manifest或CSV，也不把本輪V42診斷當成R152。
