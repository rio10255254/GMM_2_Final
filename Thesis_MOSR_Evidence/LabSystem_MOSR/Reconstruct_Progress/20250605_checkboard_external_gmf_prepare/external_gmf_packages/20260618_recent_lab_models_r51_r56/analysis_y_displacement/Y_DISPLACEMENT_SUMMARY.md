# 20250605 Lab Checkboard External GMF Y-Displacement Summary

- Package: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56`
- Parsed cases: 11
- Calibration used: 0.172500 um/px; 1 um = 5.797101 px
- Primary ranking below uses Y-step standard deviation after dropping the first scored interval, because first-step warm-up has appeared in prior same-sample GMF readouts.
- No image files were modified.

## Parsing Notes

- 06_lab_r54_edgeband_epoch020: duplicate scored filenames: ['Image__2026-06-05__16-11-19.bmp', 'Image__2026-06-05__16-13-47.bmp', 'Image__2026-06-05__16-13-55.bmp']

## Ranked Y Stability

| Rank | Case | Scored frames | Missing BMPs in score | All-step mean px | All-step std px | Skip-first mean px | Skip-first std px | Skip-first std um | Mean Score0 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 09_lab_r56_label_core_repair_best_tradeoff | 50 | 1 | 5.829551 | 0.255399 | 5.829562 | 0.258046 | 0.044513 | 99.8500 |
| 2 | 01_lab_r40_best_tradeoff_control | 50 | 1 | 5.830061 | 0.255473 | 5.829896 | 0.258118 | 0.044525 | 97.7487 |
| 3 | 02_lab_r51_mixed_psf_best_tradeoff | 50 | 1 | 5.829653 | 0.256898 | 5.829646 | 0.259560 | 0.044774 | 99.8811 |
| 4 | 10_lab_r56_label_core_repair_latest | 50 | 1 | 5.829224 | 0.257814 | 5.828854 | 0.260473 | 0.044932 | 99.7109 |
| 5 | 04_lab_r53_realistic_best_tradeoff | 50 | 1 | 5.830592 | 0.258256 | 5.829667 | 0.260852 | 0.044997 | 99.8376 |
| 6 | 00_raw_input | 50 | 1 | 5.831449 | 0.261228 | 5.831458 | 0.263935 | 0.045529 | 99.9481 |
| 7 | 08_lab_r55_source_style_latest | 50 | 1 | 5.829592 | 0.261530 | 5.829187 | 0.264225 | 0.045579 | 99.7301 |
| 8 | 07_lab_r55_source_style_best_tradeoff | 50 | 1 | 5.830959 | 0.264064 | 5.830083 | 0.266730 | 0.046011 | 99.8612 |
| 9 | 03_lab_r52_stability_latest | 50 | 1 | 5.831082 | 0.265659 | 5.829792 | 0.268260 | 0.046275 | 97.0624 |
| 10 | 05_lab_r53_realistic_latest | 38 | 13 | 5.841486 | 0.282150 | 5.841417 | 0.286042 | 0.049342 | 96.6236 |
| 11 | 06_lab_r54_edgeband_epoch020 | 62 | 1 | 4.682508 | 1.525957 | 4.663833 | 1.531692 | 0.264217 | 98.8867 |

## Interpretation Notes

- Lower Y-step standard deviation means the external GMF measured more consistent frame-to-frame Y motion on this same checkboard sequence.
- This is same-sample exploratory evidence, not a replacement for the main project formal multi-pitch external GMF baseline.
- The score files skipped the earliest BMP frames; this report keeps the package unchanged and reports the missing-frame count per case.

## Output Files

- Summary CSV: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/y_displacement_summary.csv`
- Per-step CSV: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/y_displacement_steps.csv`
- Per-frame positions CSV: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/gmf_frame_positions.csv`
- JSON: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/y_displacement_summary.json`

## Common-Frame Fairness Check

- Common scored frames across all 11 cases: 38
- Common Y steps across all 11 cases: 37
- Duplicate filenames were collapsed by first occurrence only for this fairness check; R54 still has duplicate-score caveat.

| Rank | Case | Common frames | Skip-first common std px | Skip-first common std um | Skip-first common mean px | Duplicates in original score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | 06_lab_r54_edgeband_epoch020 | 38 | 0.277154 | 0.047809 | 5.845556 | 12 |
| 2 | 09_lab_r56_label_core_repair_best_tradeoff | 38 | 0.279182 | 0.048159 | 5.844167 | 0 |
| 3 | 01_lab_r40_best_tradeoff_control | 38 | 0.280754 | 0.048430 | 5.844361 | 0 |
| 4 | 02_lab_r51_mixed_psf_best_tradeoff | 38 | 0.282725 | 0.048770 | 5.844167 | 0 |
| 5 | 10_lab_r56_label_core_repair_latest | 38 | 0.284423 | 0.049063 | 5.842917 | 0 |
| 6 | 04_lab_r53_realistic_best_tradeoff | 38 | 0.285118 | 0.049183 | 5.842417 | 0 |
| 7 | 05_lab_r53_realistic_latest | 38 | 0.286042 | 0.049342 | 5.841417 | 0 |
| 8 | 00_raw_input | 38 | 0.287241 | 0.049549 | 5.845139 | 0 |
| 9 | 08_lab_r55_source_style_latest | 38 | 0.287505 | 0.049595 | 5.841694 | 0 |
| 10 | 07_lab_r55_source_style_best_tradeoff | 38 | 0.291020 | 0.050201 | 5.842833 | 0 |
| 11 | 03_lab_r52_stability_latest | 38 | 0.292883 | 0.050522 | 5.840056 | 0 |

