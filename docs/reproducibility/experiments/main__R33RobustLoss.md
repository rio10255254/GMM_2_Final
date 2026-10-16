# main/R33RobustLoss 研究與重做紀錄

減少極端像素牽引是否改善位移穩定

p95為已核准替代；保留穩定性收益及銳利度代價，連同R34／R35／R37失敗支線

## 必要來源

R30模型、當時PSF及環形／序列來源，固定GMF讀法

## 影像保存理由

穩定性與銳利度共同展示，附不利細節案例

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [GMF_STEP_STD_METHODOLOGY.md](../../../Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md)
- [INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md](../../../Experiments/R33RobustLoss/reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md)
- [QUANTIZATION_FIX_ANALYSIS.md](../../../Experiments/R33RobustLoss/reports/QUANTIZATION_FIX_ANALYSIS.md)
- [R33_EXPERIMENT_SUMMARY.md](../../../Experiments/R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md)
- [R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md](../../../Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md)
- [r33_robust_p90_results.md](../../../Experiments/R33RobustLoss/reports/r33_robust_p90_results.md)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。
