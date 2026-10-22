# main/R32Sandbox 研究與重做紀錄

[全部實驗](../EXPERIMENTS.md) · [主線起點至R38：正式基準的形成](../routes/baseline.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

加入真實影像訓練是否改善R30

內部檢查通過但外部0.8px大幅退步；保留未採用結論

## 必要來源

R30起始模型、真實訓練影像、固定合成資料與外部GMF原始回傳

## 影像保存理由

內外部結果落差及相同視野比較

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：ROUND32_DOMAIN_CAPACITY AUDIT_0P8 Summary](<../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_SUMMARY_20260319_183506.md>)
- [原始報告：Process Probe Audit](<../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_r32_real_eq_finetune_20260319_183506.md>)
- [原始報告：ROUND32_DOMAIN_CAPACITY AUDIT_8P0 Summary](<../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_SUMMARY_20260319_183546.md>)
- [原始報告：Process Probe Audit](<../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_r32_real_eq_finetune_20260319_183546.md>)
- [原始報告：ROUND32_DOMAIN_CAPACITY Decision Memo](<../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md>)
- [原始報告：ROUND32_DOMAIN_CAPACITY Summary](<../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_SUMMARY_20260319_183506.md>)
- [原始報告：Round32 External GMF Compare: R30 B1 dironly vs R32 Sandbox Winner](<../../../Experiments/R32Sandbox/reports/ROUND32_EXTERNAL_COMPARE.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。


---

[上一個閱讀入口：main/R26NewPSFCheck](main__R26NewPSFCheck.md) · [回本分區](../routes/baseline.md) · [下一個閱讀入口：main/R33ContrastFix](main__R33ContrastFix.md)
