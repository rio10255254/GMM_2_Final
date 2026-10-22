# lab/Modern_Restoration_Benchmarks_20260719 研究與重做紀錄

[全部實驗](../EXPERIMENTS.md) · [LabSystem：校正、資料與專屬模型](../routes/lab.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。


2026-10-21保存補充：較晚計算審查優先：7月原表只有名義PI命令，Raw排序30步有選取偏向；相同輸入方式下MOSR不比Base U-Net快。9月30趟PI原拍不能回填為這批回授，尺寸／振鈴／速度與不同形貌的不利結果均保留。 [完整來源與比較脈絡](../lab_comparisons/README.md)。


比較柱、孔、線三形貌的EDSR／NAFNet等方法



30輪NAFNet與15輪EDSR各取最低驗證模型；同系統轉移且含固定光學轉換，不宣稱所有指標第一



## 必要來源



保留EDSR十五輪、NAFNet三十輪的原分組與最低驗證模型、固定光學前後處理、柱／孔／線三類來源與完整表；與R153後來的十方法比較分開。



## 影像保存理由



沿原Raw固定區域與同一成像條件選代表圖，保留光學、分塊及訓練版本差異與不利結果；原表優先，不能因沿用V42欄名而誤認方法。



## 原始方法與結果



下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。



- [原始報告：三形貌現代模型比較：正式結果報告](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/RESULTS_REPORT_ZH_TW.md>)

- [原始報告：MOSR Result Audit and Defensible Positioning](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/calculation_audit/MOSR_RESULT_AUDIT_20260719.md>)

- [原始報告：50×與20×下 EDSR-x1、NAFNet 與 MOSR 的位移比較](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/displacement_50x20x_edrs_nafnet_refresh_20260724/modern_50x20x_report/RESULTS_zh-TW.md>)

- [原始報告：現代模型逐步位移比較：建議圖說](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/displacement_50x20x_edrs_nafnet_refresh_20260724/modern_50x20x_report/trajectory_figures/CAPTIONS_zh-TW.md>)

- [原始報告：等灰階輪廓邊界位移驗證](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/isocontour_boundary_validation_20260724/VALIDATION_REPORT_zh-TW.md>)

- [原始報告：新位移量測法候選圖索引](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/measurement_method_comparison_20260724/FIGURE_INDEX_zh-TW.md>)

- [原始報告：位移邊界量測方法比較](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/measurement_method_comparison_20260724/METHOD_COMPARISON_REPORT_zh-TW.md>)

- [原始報告：EDSR-PyTorch](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/EDSR-PyTorch/README.md>)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/datasets/README.md)

- [原始報告：reproduce the GoPro dataset results](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/docs/GoPro.md>)

- [原始報告：reproduce the REDS dataset results](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/docs/REDS.md>)

- [原始報告：reproduce the SIDD dataset results](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/docs/SIDD.md>)

- [原始報告：Reproduce the Stereo SR Results](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/docs/StereoSR.md>)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/experiments/pretrained_models/README.md)

- [readme.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/NAFNet/readme.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Defocus_Deblurring/Datasets/README.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Defocus_Deblurring/README.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Defocus_Deblurring/pretrained_models/README.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Denoising/Datasets/README.md)

- [原始報告：Image Denoising](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Denoising/README.md>)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Denoising/pretrained_models/README.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Deraining/Datasets/README.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Deraining/README.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Deraining/pretrained_models/README.md)

- [原始報告：Installation](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/INSTALL.md>)

- [LICENSE.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/LICENSE.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Motion_Deblurring/Datasets/README.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Motion_Deblurring/README.md)

- [README.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/Motion_Deblurring/pretrained_models/README.md)

- [原始報告：Restormer: Efficient Transformer for High-Resolution Image Restoration (CVPR 2022 -- Oral)](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/third_party/Restormer/README.md>)



## 重做與驗證範圍



程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。

本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。

任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。



## 2026年10月16日保存核對



本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。



本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。



D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。


## 2026-10-22：這一輪在整條研究中的位置

[按R1至R153查找](../lineage/ROUND_NUMBER_MAP.md)／[本研究線的來源、得失與後續](../lineage/LAB_SYSTEM.md)。本輪上方已改為具體必要來源；原日期的保存、失敗與執行證據保留各自範圍，不以文件數或標號連續性冒稱全部歷史已重現。


---

[上一個閱讀入口：lab/BaseUNet_Baseline_20260718](lab__BaseUNet_Baseline_20260718.md) · [回本分區](../routes/lab.md) · [下一個閱讀入口：lab/MOSR_BestCheckpoint_Diagnostic_20260724](lab__MOSR_BestCheckpoint_Diagnostic_20260724.md)
