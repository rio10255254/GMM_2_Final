# main/R129_OpticalPriorHybrid 研究與重做紀錄

[全部實驗](../EXPERIMENTS.md) · [主R122至140：真實需求與量測比較](../routes/main122_140.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

恢復光學融合、抗混疊與原圖參考

短測、長訓練、80／16邊緣保留及完整LSC是不同版本；尺寸代價保留

## 必要來源

R128來源、25PSF、初始及長訓練模型、固定輸出規則

## 影像保存理由

模組活動、尺寸退步與全視野邊界帶

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R129 完整架構、設計來源與保留檢查](<../../../Experiments/R129_OpticalPriorHybrid/reports/R129_ARCHITECTURE.md>)
- [原始報告：R129 連續影像重建與 LSC 位移結果](<../../../Experiments/R129_OpticalPriorHybrid/reports/R129_CONTINUOUS_LSC_RESULTS.md>)
- [原始報告：R129 長訓練結果與完成核對](<../../../Experiments/R129_OpticalPriorHybrid/reports/R129_LONG_TRAINING_RESULTS.md>)
- [原始報告：R129：保留 V42 主要設計的接入測試](<../../../Experiments/R129_OpticalPriorHybrid/reports/R129_RESULTS.md>)
- [原始報告：R129 獨立操作套件與長訓練](<../../../Experiments/R129_OpticalPriorHybrid/reports/R129_STANDALONE_TRAINING.md>)
- [原始報告：MOSR論文改寫定稿計畫與備稿資料](<../../../Experiments/R129_OpticalPriorHybrid/reports/R129_THESIS_FINAL_REWRITE_PLAN_20260920.md>)
- [原始報告：論文只採 R129：單一模型的精簡改寫方案](<../../../Experiments/R129_OpticalPriorHybrid/reports/R129_THESIS_R128_EVIDENCE_INTEGRATION_20260920.md>)
- [原始報告：以 R129 更新論文：保留原架構的實驗與改寫計畫](<../../../Experiments/R129_OpticalPriorHybrid/reports/R129_THESIS_REVISION_PLAN.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。


2026-10-22：[重要原表、來源證據及失敗的直接閱讀入口](../project_completion/curated/IMPORTANT_TABLES_20261022.md)保留完整原列及原模型身分，無新增訓練或推論。


---

[上一個閱讀入口：main/R128_SourceOnlyFullTraining](main__R128_SourceOnlyFullTraining.md) · [回本分區](../routes/main122_140.md) · [下一個閱讀入口：main/R130_Clean](main__R130_Clean.md)
