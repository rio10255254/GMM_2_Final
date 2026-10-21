# R152_R148v2_SafeAdaptivePSF 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

保存R148v2效益並加入有作用的論文光學模組

8192擴充與930完成；位移／重拍收益保留，尺寸偏大與較慢成本不可省略

## 必要來源

可獨立重建的9216影像配方、精確PSF、基底／擴充模型、930原圖與完整讀值

## 影像保存

同視野原圖／重建、實際25PSF、30趟輪廓、尺寸與不利結果

## 原始報告

- [R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md](reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md)
- [R152_DATA_GENERATION_REPRODUCTION_20261004.md](reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md)
- [R152_DESIGN_AND_PREFLIGHT.md](reports/R152_DESIGN_AND_PREFLIGHT.md)
- [R152_FULL_REAL_VALIDATION.md](reports/R152_FULL_REAL_VALIDATION.md)
- [REPORT.md](reports/R152_RAW_FULL_RECORD_20261002/REPORT.md)
- [START_HERE.md](reports/R152_RAW_FULL_RECORD_20261002/START_HERE.md)
- [R152_SINGLE_SCAN_STEP_SD_20260930.md](reports/R152_SINGLE_SCAN_STEP_SD_20260930.md)
- [R152_STANDALONE_PACKAGE_20261004.md](reports/R152_STANDALONE_PACKAGE_20261004.md)
- [FIGURE_NOTES.md](reports/R152_THESIS_VISUAL_EVIDENCE_20261003/FIGURE_NOTES.md)
- [README_TW.md](reports/R152_THESIS_VISUAL_EVIDENCE_20261003/calibration/README_TW.md)
- [R152_TIFF_TRAINING_PACKAGE_20261004.md](reports/R152_TIFF_TRAINING_PACKAGE_20261004.md)
- [R152_TRAINING_RESULTS.md](reports/R152_TRAINING_RESULTS.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [base_model.py](base_model.py)
- [dataset.py](dataset.py)
- [losses.py](losses.py)
- [model.py](model.py)
- [optical/adaptive_fourier_psf.py](optical/adaptive_fourier_psf.py)
- [optical/fullres_psf.py](optical/fullres_psf.py)
- [reports/R152_THESIS_VISUAL_EVIDENCE_20261003/build_visual_evidence.py](reports/R152_THESIS_VISUAL_EVIDENCE_20261003/build_visual_evidence.py)
- [results/DATA_GENERATOR_20261004/build_generation_sources.py](results/DATA_GENERATOR_20261004/build_generation_sources.py)
- [results/DATA_GENERATOR_20261004/finalize_generation_package.py](results/DATA_GENERATOR_20261004/finalize_generation_package.py)
- [results/DATA_GENERATOR_20261004/portable_execution.py](results/DATA_GENERATOR_20261004/portable_execution.py)
- [results/DATA_GENERATOR_20261004/register_generation_package.py](results/DATA_GENERATOR_20261004/register_generation_package.py)
- [results/DATA_GENERATOR_20261004/run_generation_isolated.py](results/DATA_GENERATOR_20261004/run_generation_isolated.py)
- [results/DATA_GENERATOR_20261004/verify_generated_training.py](results/DATA_GENERATOR_20261004/verify_generated_training.py)
- [results/DATA_GENERATOR_20261004/verify_portable_generation.py](results/DATA_GENERATOR_20261004/verify_portable_generation.py)
- [results/DATA_GENERATOR_20261004/verify_source_probes.py](results/DATA_GENERATOR_20261004/verify_source_probes.py)
- [results/IMAGEFILE_DATASET_20261004/build_image_package.py](results/IMAGEFILE_DATASET_20261004/build_image_package.py)
- [results/IMAGEFILE_DATASET_20261004/finalize_image_package.py](results/IMAGEFILE_DATASET_20261004/finalize_image_package.py)
- [results/IMAGEFILE_DATASET_20261004/normalize_tiff_only.py](results/IMAGEFILE_DATASET_20261004/normalize_tiff_only.py)
- [results/IMAGEFILE_DATASET_20261004/probe_image_encoding.py](results/IMAGEFILE_DATASET_20261004/probe_image_encoding.py)
- [results/IMAGEFILE_DATASET_20261004/register_image_package.py](results/IMAGEFILE_DATASET_20261004/register_image_package.py)
- [results/IMAGEFILE_DATASET_20261004/verify_image_inputs.py](results/IMAGEFILE_DATASET_20261004/verify_image_inputs.py)
- [results/RAW_R152_RECALC_20261002/build_record.py](results/RAW_R152_RECALC_20261002/build_record.py)
- [results/RAW_R152_RECALC_20261002/check_and_package.py](results/RAW_R152_RECALC_20261002/check_and_package.py)
- [results/RAW_R152_RECALC_20261002/recalculate.py](results/RAW_R152_RECALC_20261002/recalculate.py)
- [results/RAW_R152_RECALC_20261002/register_record.py](results/RAW_R152_RECALC_20261002/register_record.py)
- [results/STANDALONE_PACKAGING_20261004/build_package.py](results/STANDALONE_PACKAGING_20261004/build_package.py)
- [results/STANDALONE_PACKAGING_20261004/finalize_package.py](results/STANDALONE_PACKAGING_20261004/finalize_package.py)
- [results/STANDALONE_PACKAGING_20261004/refresh_document_lock.py](results/STANDALONE_PACKAGING_20261004/refresh_document_lock.py)
- [results/STANDALONE_PACKAGING_20261004/register_package.py](results/STANDALONE_PACKAGING_20261004/register_package.py)
- [results/STANDALONE_PACKAGING_20261004/run_with_source_reads_denied.py](results/STANDALONE_PACKAGING_20261004/run_with_source_reads_denied.py)
- [results/STANDALONE_PACKAGING_20261004/verify_data_and_weights.py](results/STANDALONE_PACKAGING_20261004/verify_data_and_weights.py)
- [results/STANDALONE_PACKAGING_20261004/verify_portability.py](results/STANDALONE_PACKAGING_20261004/verify_portability.py)
- [results/THESIS_VISUAL_EVIDENCE_20261003/build_visual_evidence.py](results/THESIS_VISUAL_EVIDENCE_20261003/build_visual_evidence.py)
- [results/THESIS_VISUAL_EVIDENCE_20261003/register_visual_evidence.py](results/THESIS_VISUAL_EVIDENCE_20261003/register_visual_evidence.py)
- [results/THESIS_VISUAL_EVIDENCE_20261003/verify_visual_evidence.py](results/THESIS_VISUAL_EVIDENCE_20261003/verify_visual_evidence.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R152_R148v2_SafeAdaptivePSF.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
