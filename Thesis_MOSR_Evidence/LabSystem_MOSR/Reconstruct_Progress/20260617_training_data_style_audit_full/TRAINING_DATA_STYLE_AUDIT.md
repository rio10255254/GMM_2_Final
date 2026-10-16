# Lab Training Data Style Audit

- training_root: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data`
- sample_per_package: `0` (`0` means all pairs)
- discovered_packages: `28`
- discovered_pairs: `55784`
- sampled_pairs: `55784`

## Verdict

Risky packages exist. These packages should not be used as-is for the next Lab model.

## High-Risk Packages

| package | pairs | sampled | high | medium | problem frac | mean lbl saturation | flags |
|---|---:|---:|---:|---:|---:|---:|---|
| `r54_geometry_root_cause_probe/r54_masked_small_overfit_train` | 72 | 72 | 15 | 57 | 1.000 | 0.699 | `hard_binary_label;label_much_more_saturated_than_src` |
| `r49_cad_anchor_source/train` | 408 | 408 | 11 | 130 | 0.346 | 0.283 | `hard_binary_label;label_much_more_saturated_than_src` |
| `r49_cad_anchor_source/test` | 48 | 48 | 0 | 29 | 0.604 | 0.396 | `label_much_more_saturated_than_src` |

## Medium / Mixed Packages

| package | pairs | sampled | high | medium | low | flags |
|---|---:|---:|---:|---:|---:|---|
| `r53_realistic_dataset_calibration/r53_realistic_calibrated_train_6000` | 6000 | 6000 | 20 | 173 | 5807 | `hard_binary_label;label_contrast_style_jump;label_much_more_saturated_than_src;large_src_label_shift;low_src_label_correspondence` |
| `r49_cad_anchor_real_geometry/r49_cad_anchor_train_4000` | 4000 | 4000 | 20 | 160 | 3820 | `hard_binary_label;label_contrast_style_jump;label_much_more_saturated_than_src;large_src_label_shift;low_src_label_correspondence` |
| `foundation_bads_psf` | 11168 | 11168 | 9 | 92 | 11067 | `hard_binary_label;label_contrast_style_jump;label_much_more_saturated_than_src;large_src_label_shift;low_src_label_correspondence` |
| `r48_real_corner_transfer/r48_real_corner_train_6000` | 6000 | 6000 | 9 | 49 | 5942 | `hard_binary_label;label_contrast_style_jump;label_much_more_saturated_than_src;large_src_label_shift;low_src_label_correspondence` |
| `r47_realistic_boundary_generalization/r47_realistic_boundary_train_4000` | 4000 | 4000 | 9 | 40 | 3951 | `hard_binary_label;label_contrast_style_jump;label_much_more_saturated_than_src;large_src_label_shift;low_src_label_correspondence` |
| `r40_microscopy_feature_coverage/r40_micro_capacity_train` | 1300 | 1300 | 6 | 16 | 1278 | `label_contrast_style_jump;large_src_label_shift;low_src_label_correspondence` |
| `r52_corner_stability_guard/r52_corner_stability_train_4000` | 4000 | 4000 | 5 | 27 | 3968 | `label_contrast_style_jump;label_much_more_saturated_than_src;large_src_label_shift;low_src_label_correspondence` |
| `r46_corner_aware_finetune/r46_checkboard_corner_train` | 1550 | 1550 | 5 | 11 | 1534 | `label_contrast_style_jump;large_src_label_shift;low_src_label_correspondence` |
| `r51_blur_source_probe/r51_gaussian_corner_probe` | 1550 | 1550 | 5 | 11 | 1534 | `label_contrast_style_jump;large_src_label_shift;low_src_label_correspondence` |
| `r51_blur_source_probe/r51_mixed_psf_corner_probe` | 1550 | 1550 | 5 | 11 | 1534 | `label_contrast_style_jump;large_src_label_shift;low_src_label_correspondence` |
| `r51_blur_source_probe/r51_weak_bads_corner_probe` | 1550 | 1550 | 5 | 11 | 1534 | `label_contrast_style_jump;large_src_label_shift;low_src_label_correspondence` |
| `foundation_gaussian_control` | 3468 | 3468 | 2 | 16 | 3450 | `hard_binary_label;label_contrast_style_jump` |
| `r39_shape_generalization/shape_val_unseen` | 210 | 210 | 2 | 0 | 208 | `hard_binary_label;label_much_more_saturated_than_src` |
| `r40_microscopy_feature_coverage/micro_val_unseen` | 100 | 100 | 1 | 4 | 95 | `label_contrast_style_jump;low_src_label_correspondence` |
| `r53_realistic_dataset_calibration/r53_realistic_calibrated_val` | 1740 | 1740 | 0 | 17 | 1723 | `label_much_more_saturated_than_src` |
| `r48_real_corner_transfer/real_corner_val_unseen` | 1200 | 1200 | 0 | 14 | 1186 | `label_much_more_saturated_than_src` |
| `r47_realistic_boundary_generalization/realistic_boundary_val_unseen` | 800 | 800 | 0 | 9 | 791 | `label_much_more_saturated_than_src` |
| `r52_corner_stability_guard/r52_corner_stability_val` | 700 | 700 | 0 | 5 | 695 | `label_much_more_saturated_than_src` |

## Files

- package summary: `package_style_summary.csv`
- sampled pair metrics: `pair_style_sample_metrics.csv`
- worst-case visual sheet: `worst_style_contact_sheet.png`

## Audit Rules

- High risk: label is hard binary/CAD-like, has very weak source-label correspondence, or shape/read errors.
- Medium risk: label contrast/saturation differs strongly from source, but not enough to prove a broken pair.
- Low risk: label keeps a source-like grayscale style under these checks.
- Package is listed as risky when high-risk samples exceed 10% or high+medium samples exceed 25%.
