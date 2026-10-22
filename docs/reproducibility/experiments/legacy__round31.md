# legacy/round31 研究與重做紀錄

[直接查看這一輪的檔案分工](<../../../Traing_Progress/organized_20260316/round31/FILE_GUIDE.md>)

[全部實驗](../EXPERIMENTS.md) · [早期批次與歷史支線](../routes/early.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

訓練權重與等化訊號再調整

外部退步，不能只看內部通過

## 必要來源

從固定R30基準做已量測超參數候選，保存所有外部回傳與主尺度退步；原研究分支與完整失敗表可從歷史版本取得。

## 影像保存理由

按當輪實際測過的尺度保留原圖／重建、步長及失敗比較；內部量法、外部回傳與跨輪共用參考須在圖說分清，不把尚缺回傳的格子補成結果。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：ROUND31_B1_HYPERPARAM AUDIT_0P8 Summary](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_0P8_SUMMARY_20260318_113707.md>)
- [原始報告：Process Probe Audit](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_0P8_r31_edge_ratio_low_20260318_113707.md>)
- [原始報告：Process Probe Audit](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_0P8_r31_eq_combo_20260318_113707.md>)
- [原始報告：Process Probe Audit](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_0P8_r31_eq_prob_up_20260318_113707.md>)
- [原始報告：Process Probe Audit](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_0P8_r31_eq_weight_up_20260318_113707.md>)
- [原始報告：ROUND31_B1_HYPERPARAM AUDIT_8P0 Summary](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_8P0_SUMMARY_20260318_113834.md>)
- [原始報告：Process Probe Audit](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_8P0_r31_edge_ratio_low_20260318_113834.md>)
- [原始報告：Process Probe Audit](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_8P0_r31_eq_combo_20260318_113834.md>)
- [原始報告：Process Probe Audit](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_8P0_r31_eq_prob_up_20260318_113834.md>)
- [原始報告：Process Probe Audit](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_AUDIT_8P0_r31_eq_weight_up_20260318_113834.md>)
- [原始報告：ROUND31_B1_HYPERPARAM Decision Memo](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md>)
- [原始報告：ROUND31_B1_HYPERPARAM Summary](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_SUMMARY_20260318_113707.md>)
- [原始報告：Round31 External GMF Compare: R30 B1 dironly vs R31 Candidates](<../../../Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_EXTERNAL_COMPARE.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。

## 2026-10-22：這一輪在整條研究中的位置

[按R1至R153查找](../lineage/ROUND_NUMBER_MAP.md)／[本研究線的來源、得失與後續](../lineage/EARLY_ROUNDS.md)。本輪上方已改為具體必要來源；原日期的保存、失敗與執行證據保留各自範圍，不以文件數或標號連續性冒稱全部歷史已重現。


---

[上一個閱讀入口：legacy/round30](legacy__round30.md) · [回本分區](../routes/early.md) · [下一個閱讀入口：legacy/round32](legacy__round32.md)
