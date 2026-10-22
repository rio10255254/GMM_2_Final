# lab/R50_PSFControlDiagnosis 研究與重做紀錄

[Lab逐輪必要來源與代表模型核對](<../round_source_reviews/LAB_SYSTEM_20261023.md>)

[直接查看這一輪的檔案分工](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R50_PSFControlDiagnosis/FILE_GUIDE.md>)

[全部實驗](../EXPERIMENTS.md) · [LabSystem：校正、資料與專屬模型](../routes/lab.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

診斷Lab光學模糊是否過強

只做診斷；完整BADS比實拍更軟，混合光學需另試

## 必要來源

同一stage48角點比較實拍、正式BADS、高斯及弱BADS alpha0.50／0.75；保留原邊寬、梯度表和控制生成設定。這是模糊來源診斷，沒有新的正式訓練模型。

## 影像保存理由

比較同一stage48控制與實拍的邊寬、灰階剖面及光學差異；保留正式BADS過強與高斯控制，不把控制影像當新原拍。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R50 PSF Control Diagnosis](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R50_PSFControlDiagnosis/reports/R50_RESULTS.md>)

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


---

[上一個閱讀入口：lab/R49_CADAnchorRealGeometry](lab__R49_CADAnchorRealGeometry.md) · [回本分區](../routes/lab.md) · [下一個閱讀入口：lab/R51_BlurSourceProbe](lab__R51_BlurSourceProbe.md)
