# main/R148_MeasurementStableNativePSF 研究與重做紀錄

把決定邊界的主幹全部留在原尺寸

正式只留下62次且無保存點；累積依賴超出訓練邊界，不續跑

## 必要來源

3072視圖生成配方、64次前測與62次失敗、架構審查

## 影像保存理由

有效邊界範圍與位置一致性控制

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [R148_ARCHITECTURE_REVIEW.md](../../../Experiments/R148_MeasurementStableNativePSF/reports/R148_ARCHITECTURE_REVIEW.md)
- [R148_IMPLEMENTATION.md](../../../Experiments/R148_MeasurementStableNativePSF/reports/R148_IMPLEMENTATION.md)
- [R148_VALIDATION_PLAN.md](../../../Experiments/R148_MeasurementStableNativePSF/reports/R148_VALIDATION_PLAN.md)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。
