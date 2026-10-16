# main/R33RobustLoss 研究與重做紀錄

減少極端像素牽引是否改善位移穩定

p95為已核准替代；保留穩定性收益及銳利度代價，連同R34／R35／R37失敗支線

## 必要來源

R30模型、當時PSF及環形／序列來源，固定GMF讀法

## 影像保存理由

穩定性與銳利度共同展示，附不利細節案例

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：GMF step_std 計算方法論](<../../../Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md>)
- [原始報告：Internal vs External Step_std 偏差分析](<../../../Experiments/R33RobustLoss/reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md>)
- [原始報告：推理量化修復分析](<../../../Experiments/R33RobustLoss/reports/QUANTIZATION_FIX_ANALYSIS.md>)
- [原始報告：R33 Robust Loss — Experiment Summary](<../../../Experiments/R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md>)
- [原始報告：R33-R38v2 完整實驗系列報告](<../../../Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md>)
- [原始報告：R33 robust_p90 Results (2026-04-05)](<../../../Experiments/R33RobustLoss/reports/r33_robust_p90_results.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。
