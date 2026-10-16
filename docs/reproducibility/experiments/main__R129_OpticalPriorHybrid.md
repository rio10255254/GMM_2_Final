# main/R129_OpticalPriorHybrid 研究與重做紀錄

恢復光學融合、抗混疊與原圖參考

短測、長訓練、80／16邊緣保留及完整LSC是不同版本；尺寸代價保留

## 必要來源

R128來源、25PSF、初始及長訓練模型、固定輸出規則

## 影像保存理由

模組活動、尺寸退步與全視野邊界帶

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [R129_ARCHITECTURE.md](../../../Experiments/R129_OpticalPriorHybrid/reports/R129_ARCHITECTURE.md)
- [R129_CONTINUOUS_LSC_RESULTS.md](../../../Experiments/R129_OpticalPriorHybrid/reports/R129_CONTINUOUS_LSC_RESULTS.md)
- [R129_LONG_TRAINING_RESULTS.md](../../../Experiments/R129_OpticalPriorHybrid/reports/R129_LONG_TRAINING_RESULTS.md)
- [R129_RESULTS.md](../../../Experiments/R129_OpticalPriorHybrid/reports/R129_RESULTS.md)
- [R129_STANDALONE_TRAINING.md](../../../Experiments/R129_OpticalPriorHybrid/reports/R129_STANDALONE_TRAINING.md)
- [R129_THESIS_FINAL_REWRITE_PLAN_20260920.md](../../../Experiments/R129_OpticalPriorHybrid/reports/R129_THESIS_FINAL_REWRITE_PLAN_20260920.md)
- [R129_THESIS_R128_EVIDENCE_INTEGRATION_20260920.md](../../../Experiments/R129_OpticalPriorHybrid/reports/R129_THESIS_R128_EVIDENCE_INTEGRATION_20260920.md)
- [R129_THESIS_REVISION_PLAN.md](../../../Experiments/R129_OpticalPriorHybrid/reports/R129_THESIS_REVISION_PLAN.md)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。
