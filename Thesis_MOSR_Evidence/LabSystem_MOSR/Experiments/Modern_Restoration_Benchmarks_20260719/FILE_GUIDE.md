# lab/Modern_Restoration_Benchmarks_20260719：檔案怎麼找

[本輪研究卡](<../../../../docs/reproducibility/experiments/lab__Modern_Restoration_Benchmarks_20260719.md>) · [全部研究分區](<../../../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../../../docs/reproducibility/STATUS.md>)

**研究問題：比較柱、孔、線三形貌的EDSR／NAFNet等方法。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [三形貌現代模型比較：正式結果報告](<evaluation/RESULTS_REPORT_ZH_TW.md>)
- [MOSR Result Audit and Defensible Positioning](<evaluation/calculation_audit/MOSR_RESULT_AUDIT_20260719.md>)
- [50×與20×下 EDSR-x1、NAFNet 與 MOSR 的位移比較](<evaluation/displacement_50x20x_edrs_nafnet_refresh_20260724/modern_50x20x_report/RESULTS_zh-TW.md>)
- [現代模型逐步位移比較：建議圖說](<evaluation/displacement_50x20x_edrs_nafnet_refresh_20260724/modern_50x20x_report/trajectory_figures/CAPTIONS_zh-TW.md>)
- [等灰階輪廓邊界位移驗證](<evaluation/isocontour_boundary_validation_20260724/VALIDATION_REPORT_zh-TW.md>)
- [新位移量測法候選圖索引](<evaluation/measurement_method_comparison_20260724/FIGURE_INDEX_zh-TW.md>)

其餘原報告見[本輪完整研究卡](<../../../../docs/reproducibility/experiments/lab__Modern_Restoration_Benchmarks_20260719.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [analyze_circular_cd_sharpness.py](<analyze_circular_cd_sharpness.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [analyze_isocontour_boundary_displacement.py](<analyze_isocontour_boundary_displacement.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [analyze_line_multimethod.py](<analyze_line_multimethod.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [analyze_multimethod_displacement.py](<analyze_multimethod_displacement.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [audit_calculation_integrity.py](<audit_calculation_integrity.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [audit_line_selection_sensitivity.py](<audit_line_selection_sensitivity.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [audit_mosr_step_selection.py](<audit_mosr_step_selection.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [audit_selection_sensitivity.py](<audit_selection_sensitivity.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [benchmark_models.py](<benchmark_models.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [benchmark_runtime_fair_modes.py](<benchmark_runtime_fair_modes.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [build_50x20x_modern_displacement_report.py](<build_50x20x_modern_displacement_report.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [build_modern_model_trajectory_data.py](<build_modern_model_trajectory_data.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [build_result_report.py](<build_result_report.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [compare_displacement_measurement_methods.py](<compare_displacement_measurement_methods.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluation/](<evaluation/README.md>) | 82檔 | 量測介面、固定參照、設定或比較內容 |
| [export_isocontour_qa_overlays.py](<export_isocontour_qa_overlays.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [export_method_crops.py](<export_method_crops.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [infer_modern_baseline.py](<infer_modern_baseline.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [models_modern.py](<models_modern.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [package_final_results.py](<package_final_results.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [plot_50x20x_modern_displacement.m](<plot_50x20x_modern_displacement.m>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [plot_benchmark_results.m](<plot_benchmark_results.m>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [plot_measurement_method_comparison.m](<plot_measurement_method_comparison.m>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [plot_modern_model_trajectories.m](<plot_modern_model_trajectories.m>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [prepare_via_reference.py](<prepare_via_reference.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [run_edsr_after_naf.ps1](<run_edsr_after_naf.ps1>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [run_final_pipeline_after_training.ps1](<run_final_pipeline_after_training.ps1>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [third_party/](<third_party>) | 260檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [train_modern_baseline.py](<train_modern_baseline.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [validate_final_benchmark.py](<validate_final_benchmark.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |

## 必要來源與取得界線

保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。。

[按用途取得原件](<../../../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
