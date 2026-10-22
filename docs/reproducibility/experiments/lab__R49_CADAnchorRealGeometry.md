# lab/R49_CADAnchorRealGeometry 研究與重做紀錄

加入可靠區域內的實體CAD答案

100輪仍使角點退步；可靠遮罩很小，不能當全圖答案

## 必要來源

從Lab R40 best起步，用4000組訓練與120組保留CAD錨點；必須保留可信遮罩、遮罩外原樣答案、100輪與三種原模型的角點表。局部CAD不能冒充全圖真值。

## 影像保存理由

以51張棋盤相同角點的原圖／重建、位移分布與失敗尾端作代表；同時呈現中位與大偏移，模型重建不能當幾何真值。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：Lab R49 Checkboard Validation - 2026-06-14](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R49_CADAnchorRealGeometry/reports/R49_CHECKBOARD_VALIDATION_20260614.md>)
- [原始報告：R49 Failure Analysis - 2026-06-14](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R49_CADAnchorRealGeometry/reports/R49_FAILURE_ANALYSIS_20260614.md>)
- [原始報告：R49 Results - 2026-06-14](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R49_CADAnchorRealGeometry/reports/R49_RESULTS_20260614.md>)

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
