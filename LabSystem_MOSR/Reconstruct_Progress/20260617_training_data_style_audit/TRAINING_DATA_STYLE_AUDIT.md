# Lab Training Data Style Audit

- training_root: `LabSystem_MOSR/Training_Data`
- sample_per_package: `160` (`0` means all pairs)
- discovered_packages: `28`
- discovered_pairs: `55784`
- sampled_pairs: `4020`

## Verdict

No package crossed the high-risk majority threshold in the sampled audit.

## High-Risk Packages

| package | pairs | sampled | high | mean lbl saturation | mean abs diff | flags |
|---|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 |  |

## Medium / Mixed Packages

| package | pairs | sampled | high | medium | low | flags |
|---|---:|---:|---:|---:|---:|---|
| `r54_geometry_root_cause_probe/r54_masked_small_overfit_train` | 72 | 72 | 15 | 57 | 0 | `hard_binary_label;label_much_more_saturated_than_src` |
| `r49_cad_anchor_source/train` | 408 | 160 | 4 | 48 | 108 | `hard_binary_label;label_much_more_saturated_than_src` |
| `r51_blur_source_probe/r51_gaussian_corner_probe` | 1550 | 160 | 2 | 1 | 157 | `label_contrast_style_jump;low_src_label_correspondence` |
| `r39_shape_generalization/shape_val_unseen` | 210 | 160 | 2 | 0 | 158 | `hard_binary_label;label_much_more_saturated_than_src` |
| `r49_cad_anchor_real_geometry/r49_cad_anchor_train_4000` | 4000 | 160 | 1 | 7 | 152 | `label_contrast_style_jump;label_much_more_saturated_than_src;large_src_label_shift` |
| `r40_microscopy_feature_coverage/micro_val_unseen` | 100 | 100 | 1 | 4 | 95 | `label_contrast_style_jump;low_src_label_correspondence` |
| `r46_corner_aware_finetune/r46_checkboard_corner_train` | 1550 | 160 | 1 | 1 | 158 | `label_contrast_style_jump;low_src_label_correspondence` |
| `r49_cad_anchor_source/test` | 48 | 48 | 0 | 29 | 19 | `label_much_more_saturated_than_src` |
| `r47_realistic_boundary_generalization/realistic_boundary_val_unseen` | 800 | 160 | 0 | 3 | 157 | `label_much_more_saturated_than_src` |
| `r53_realistic_dataset_calibration/r53_realistic_calibrated_train_6000` | 6000 | 160 | 0 | 3 | 157 | `label_contrast_style_jump;label_much_more_saturated_than_src` |
| `foundation_bads_psf` | 11168 | 160 | 0 | 2 | 158 | `label_contrast_style_jump;label_much_more_saturated_than_src` |
| `r48_real_corner_transfer/real_corner_val_unseen` | 1200 | 160 | 0 | 2 | 158 | `label_much_more_saturated_than_src` |
| `r51_blur_source_probe/r51_mixed_psf_corner_probe` | 1550 | 160 | 0 | 2 | 158 | `label_contrast_style_jump` |
| `r52_corner_stability_guard/r52_corner_stability_val` | 700 | 160 | 0 | 2 | 158 | `label_much_more_saturated_than_src` |
| `r47_realistic_boundary_generalization/r47_realistic_boundary_train_4000` | 4000 | 160 | 0 | 1 | 159 | `label_contrast_style_jump` |
| `r48_real_corner_transfer/r48_real_corner_train_6000` | 6000 | 160 | 0 | 1 | 159 | `label_contrast_style_jump` |
| `r51_blur_source_probe/r51_weak_bads_corner_probe` | 1550 | 160 | 0 | 1 | 159 | `label_contrast_style_jump` |
| `r52_corner_stability_guard/r52_corner_stability_train_4000` | 4000 | 160 | 0 | 1 | 159 | `label_contrast_style_jump` |
| `r53_realistic_dataset_calibration/r53_realistic_calibrated_val` | 1740 | 160 | 0 | 1 | 159 | `label_much_more_saturated_than_src` |

## Files

- package summary: `package_style_summary.csv`
- sampled pair metrics: `pair_style_sample_metrics.csv`
- worst-case visual sheet: `worst_style_contact_sheet.png`

## Audit Rules

- High risk: label is hard binary/CAD-like, has very weak source-label correspondence, or shape/read errors.
- Medium risk: label contrast/saturation differs strongly from source, but not enough to prove a broken pair.
- Low risk: label keeps a source-like grayscale style under these checks.
