# lab/R53_RealisticDatasetCalibration 研究與重做紀錄

重新平衡環形、形狀、顯微、背景與CAD資料

6000組／100輪從零完成但實體角點失敗；已清理批次不重算回收

## 必要來源

6000組重新平衡環、形狀、顯微、角點、背景與CAD，1740組驗證；保留R49可信遮罩與三種角點光學。從零100輪的batch16／workers4／關閉PSF-forward設定，以及OOM、Windows工作程序失敗和過慢嘗試都屬必要脈絡。

## 影像保存理由

以51張棋盤相同角點的原圖／重建、位移分布與失敗尾端作代表；同時呈現中位與大偏移，模型重建不能當幾何真值。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：Lab R53 Realistic Dataset Calibration Checkboard Validation - 2026-06-16](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R53_RealisticDatasetCalibration/reports/R53_CHECKBOARD_VALIDATION.md>)
- [原始報告：R53_RESULTS](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R53_RealisticDatasetCalibration/reports/R53_RESULTS.md>)

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
