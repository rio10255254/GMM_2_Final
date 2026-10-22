# main/R153_MeanExternalBenchmark 研究與重做紀錄

[全部實驗](../EXPERIMENTS.md) · [主R141起：光學配對與論文比較](../routes/main141_plus.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

用九顆平均位移與外部架構完成論文比較

十方法930張／30趟完成，兩官方後端受阻；各自訓練目標與不等輪數如實保留

## 精選的小型閱讀內容（2026-10-21）

[原18,000筆位移表](../../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/data/full_benchmark/all_displacements.csv)為2,620,815 bytes，包含相鄰步與相對起點各9,000筆；兩種基準使用同批30趟掃描，不當作獨立重拍。[完整小型內容清單](../project_completion/curated/R153_LIGHTWEIGHT_CONTENT.json)列出15份原CSV、三張原報告圖及七個原選模記錄。數表合計2,810,403 bytes，三圖合計363,062 bytes；原程式、數值和圖像不改寫，不再上傳每張重建的完整像素陣列。

七個外部模型依原訓練完成收據選定，實際訓練輪數與選用輪次分開；RAW、Wiener不額外製造神經模型。模型引用既有已發布的精確相同檔案，不重傳；U-Net與MambaIRv2的原阻礙、SEM尺寸差、長距離與速度代價仍隨完整表格保留。此整理沒有重新推論或重算研究指標。

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


---

[上一個閱讀入口：main/R152_R148v2_SafeAdaptivePSF](main__R152_R148v2_SafeAdaptivePSF.md) · [回本分區](../routes/main141_plus.md)
