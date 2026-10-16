# main/R153_MeanExternalBenchmark 研究與重做紀錄

用九顆平均位移與外部架構完成論文比較

十方法930張／30趟完成，兩官方後端受阻；各自訓練目標與不等輪數如實保留

## 必要來源

共同R152生成資料、七個官方來源／實際改動／模型、完整圓心／邊界／PI／效率讀值

## 影像保存理由

十方法同視野比較、原生影像、最差情況及全部灰階論文圖

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：已完成模型的新重建效率比較](<../../../Experiments/R153_MeanExternalBenchmark/reports/AVAILABLE_MODELS_EFFICIENCY.md>)
- [原始報告：已完成模型之完整實拍驗證與效率比較](<../../../Experiments/R153_MeanExternalBenchmark/reports/AVAILABLE_MODELS_PROGRESS.md>)
- [原始報告：已完成模型之完整實拍驗證與效率比較](<../../../Experiments/R153_MeanExternalBenchmark/reports/AVAILABLE_MODELS_REAL_RESULTS.md>)
- [原始報告：已完成方法之論文比較交接](<../../../Experiments/R153_MeanExternalBenchmark/reports/AVAILABLE_MODELS_STAGE_COMPLETE/REPORT.md>)
- [原始報告：已完成方法之論文比較交接](<../../../Experiments/R153_MeanExternalBenchmark/reports/AVAILABLE_MODELS_STAGE_PROGRESS/REPORT.md>)
- [原始報告：外部模型比較結果與完成狀態](<../../../Experiments/R153_MeanExternalBenchmark/reports/BENCHMARK_RESULTS.md>)
- [原始報告：已完成模型的新重建效率比較](<../../../Experiments/R153_MeanExternalBenchmark/reports/COMPLETED_MODELS_EFFICIENCY.md>)
- [原始報告：已完成模型之完整實拍驗證與效率比較](<../../../Experiments/R153_MeanExternalBenchmark/reports/COMPLETED_MODELS_RESULTS.md>)
- [原始報告：九方法論文修改位置與交付檢查](<../../../Experiments/R153_MeanExternalBenchmark/reports/COMPLETED_MODELS_THESIS_HANDOFF/PAPER_UPDATE_GUIDE.md>)
- [原始報告：已完成方法之論文比較交接](<../../../Experiments/R153_MeanExternalBenchmark/reports/COMPLETED_MODELS_THESIS_HANDOFF/REPORT.md>)
- [原始報告：已完成模型的新重建效率比較](<../../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_EFFICIENCY.md>)
- [原始報告：已完成模型之完整實拍驗證與效率比較](<../../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_RESULTS.md>)
- [原始報告：十方法論文修改位置與交付檢查](<../../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/PAPER_UPDATE_GUIDE.md>)
- [原始報告：已完成方法之論文比較交接](<../../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md>)
- [原始報告：九顆柱體平均位移與中位數位移比較](<../../../Experiments/R153_MeanExternalBenchmark/reports/MEAN_MEDIAN_RESULTS.md>)
- [原始報告：MOSR論文修改交接：九顆平均位移之完整驗證結果](<../../../Experiments/R153_MeanExternalBenchmark/reports/MOSR_MEAN_THESIS_HANDOFF_20261005/MOSR_MEAN_THESIS_HANDOFF.md>)
- [原始報告：最新可直接使用：十方法完整論文資料（2026-10-07）](<../../../Experiments/R153_MeanExternalBenchmark/reports/THESIS_UPDATE_MAP.md>)
- [原始報告：外部模型訓練與驗證監看已完成](<../../../Experiments/R153_MeanExternalBenchmark/reports/TRAINING_MONITOR.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次已實跑本輪的完整資料生成或保存觀測重算；實測範圍見總入口，並不表示重跑過所有歷史訓練。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。
