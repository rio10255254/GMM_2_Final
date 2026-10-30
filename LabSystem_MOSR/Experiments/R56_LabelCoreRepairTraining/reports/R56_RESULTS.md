# R56 Results

## Purpose

R56 tests the label-core repaired training data after the R55 label audit found
that the source-style labels were better than fake binary labels, but still too
soft in some core regions.

## Current Plan

- Use the repaired 6000-pair R53/R55-style package as the first formal training
  set.
- Keep the validation pool out of training for held-out visual and metric checks.
- Preserve the R55 training recipe: scratch training, batch 16, 4 workers,
  boundary geometry enabled, and PSF-forward loss disabled.

## Status

- Data QA completed before training.
- Launcher and tests are prepared.
- Formal 50-epoch training completed.
- Real checkboard reconstruction completed for best_tradeoff and latest.
- Real checkboard corner validation failed.

## Result

| Case | Median corner shift | Tail shift | Corners > 5 px |
|---|---:|---:|---:|
| Lab R40 tradeoff control | 4.243 px | 5.000 px | 24.581% |
| R55 best_tradeoff | 2.828 px | 3.606 px | 21.788% |
| R56 best_tradeoff | 2.828 px | 9.899 px | 26.816% |
| R56 latest | 9.899 px | 9.899 px | 59.777% |

R56 is not adopted. The label-core repair did not improve the real checkboard
corner result over R55. It preserved the good median of R55 best_tradeoff, but
made the large-shift tail worse. The latest checkpoint again confirms that
internal validation PSNR/SSIM can keep improving while real-corner geometry
degrades.

## Training Summary

- Run: `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r56_label_core_repair_r53_scratch_formal_label_core_repair_e050_b016_w04_nophys_20260618_122705`
- Final internal validation: `PSNR 26.40`, `SSIM 0.9333`
- Best internal validation epoch: 50
- Real-corner selected checkpoint: none; R55 best remains the better Lab candidate

## Artifacts

- Checkboard validation: `reports/R56_CHECKBOARD_VALIDATION.md`
- Training log summary: `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r56_label_core_repair_r53_scratch_formal_label_core_repair_e050_b016_w04_nophys_20260618_122705/r56_training_log_summary.json`
- GMF-ready best folder: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r56_label_core_repair_best_tradeoff`
- GMF-ready latest folder: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r56_label_core_repair_latest`
