# lab/Modern_Restoration_Benchmarks_20260719 研究與重做紀錄

比較柱、孔、線三形貌的EDSR／NAFNet等方法

30輪NAFNet與15輪EDSR各取最低驗證模型；同系統轉移且含固定光學轉換，不宣稱所有指標第一

## 必要來源

保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。

## 影像保存理由

共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [RESULTS_REPORT_ZH_TW.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/RESULTS_REPORT_ZH_TW.md)
- [MOSR_RESULT_AUDIT_20260719.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/calculation_audit/MOSR_RESULT_AUDIT_20260719.md)
- [RESULTS_zh-TW.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/displacement_50x20x_edrs_nafnet_refresh_20260724/modern_50x20x_report/RESULTS_zh-TW.md)
- [CAPTIONS_zh-TW.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/displacement_50x20x_edrs_nafnet_refresh_20260724/modern_50x20x_report/trajectory_figures/CAPTIONS_zh-TW.md)
- [VALIDATION_REPORT_zh-TW.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/isocontour_boundary_validation_20260724/VALIDATION_REPORT_zh-TW.md)
- [FIGURE_INDEX_zh-TW.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/measurement_method_comparison_20260724/FIGURE_INDEX_zh-TW.md)
- [METHOD_COMPARISON_REPORT_zh-TW.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/measurement_method_comparison_20260724/METHOD_COMPARISON_REPORT_zh-TW.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/EDSR-PyTorch/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/datasets/README.md)
- [GoPro.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/docs/GoPro.md)
- [REDS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/docs/REDS.md)
- [SIDD.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/docs/SIDD.md)
- [StereoSR.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/docs/StereoSR.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/experiments/pretrained_models/README.md)
- [readme.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/readme.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Defocus_Deblurring/Datasets/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Defocus_Deblurring/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Defocus_Deblurring/pretrained_models/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Denoising/Datasets/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Denoising/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Denoising/pretrained_models/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Deraining/Datasets/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Deraining/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Deraining/pretrained_models/README.md)
- [INSTALL.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/INSTALL.md)
- [LICENSE.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/LICENSE.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Motion_Deblurring/Datasets/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Motion_Deblurring/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Motion_Deblurring/pretrained_models/README.md)
- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/README.md)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。
