# main/R39_ShapeGeneralization 研究與重做紀錄

[本輪與共用主線的來源、原表及模型關係](../round_source_reviews/BASELINE_20261023.md)

[直接查看這一輪的檔案分工](<../../../Experiments/R39_ShapeGeneralization/FILE_GUIDE.md>)

[全部實驗](../EXPERIMENTS.md) · [主R39至62：形狀、顯微與量測](../routes/main39_62.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

保留環形能力並擴大非環形重建

端點與權重平均版需分開；跨R39／R40的a025是核准平衡替代

## 必要來源

COMBO、R39與R40端點、平均比例、形狀生成及固定分組

## 影像保存理由

七類形狀及三尺度量測，保留平均前後差異

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R39 a030 在多樣顯微圖形上的詳細評估](<../../../Experiments/R39_ShapeGeneralization/reports/R39_A030_MICROSCOPY_EVALUATION.md>)
- [原始報告：R39 外部 GMF 比較 — `r39_combo_strong_avg_a030`](<../../../Experiments/R39_ShapeGeneralization/reports/R39_EXTERNAL_COMPARE.md>)
- [原始報告：R39 結果 — 多形狀泛化](<../../../Experiments/R39_ShapeGeneralization/reports/R39_RESULTS.md>)
- [原始報告：R39R40 a025 ONNX 交付包內容審核](<../../../Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_A025_ONNX_PACKAGE_CONTENT_AUDIT_20260513.md>)
- [原始報告：R39R40 a025 全面能力評估](<../../../Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md>)
- [原始報告：R40 External GMF Compare - `r39r40_avg_a025`](<../../../Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_EXTERNAL_COMPARE.md>)
- [原始報告：R39R40 a025 Rayleigh-aware 邊角細節診斷](<../../../Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC.md>)
- [原始報告：R39R40 a025 Rayleigh 診斷補充驗證 — 統計檢驗篇](<../../../Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC_VALIDATION.md>)
- [原始報告：a025 Rayleigh 診斷補充:訓練分布對齊 + 視覺驗證](<../../../Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_RAYLEIGH_VISUAL_AND_DISTRIBUTION.md>)
- [原始報告：R40 External GMF Compare - `r39r40_avg_a050`](<../../../Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a050_EXTERNAL_COMPARE.md>)
- [原始報告：R40 External GMF Compare - `r39r40_avg_a075`](<../../../Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a075_EXTERNAL_COMPARE.md>)
- [原始報告：R39 a030 × R40 a043 互補權重平均 — 外部 GMF 補測結果](<../../../Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_COMPLEMENTARY_AVG_RESULTS.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。


---

[回本分區](../routes/main39_62.md) · [下一個閱讀入口：main/R40_MicroscopyFeatureCoverage](main__R40_MicroscopyFeatureCoverage.md)
