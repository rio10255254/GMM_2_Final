# Lab Training Data Style Audit

- training_root: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data`
- sample_per_package: `8` (`0` means all pairs)
- discovered_packages: `28`
- discovered_pairs: `55784`
- sampled_pairs: `224`

## Verdict

Risky packages exist. These packages should not be used as-is for the next Lab model.

## High-Risk Packages

| package | pairs | sampled | high | medium | problem frac | mean lbl saturation | flags |
|---|---:|---:|---:|---:|---:|---:|---|
| `r54_geometry_root_cause_probe/r54_masked_small_overfit_train` | 72 | 8 | 5 | 3 | 1.000 | 0.815 | `hard_binary_label;label_much_more_saturated_than_src` |
| `r40_microscopy_feature_coverage/micro_val_unseen` | 100 | 8 | 1 | 0 | 0.125 | 0.001 | `label_contrast_style_jump;low_src_label_correspondence` |
| `r49_cad_anchor_source/test` | 48 | 8 | 0 | 6 | 0.750 | 0.424 | `label_much_more_saturated_than_src` |
| `r49_cad_anchor_source/train` | 408 | 8 | 0 | 4 | 0.500 | 0.350 | `label_much_more_saturated_than_src` |

## Medium / Mixed Packages

| package | pairs | sampled | high | medium | low | flags |
|---|---:|---:|---:|---:|---:|---|
| `r46_corner_aware_finetune/r46_checkboard_corner_train` | 1550 | 8 | 0 | 1 | 7 | `label_contrast_style_jump` |
| `r51_blur_source_probe/r51_weak_bads_corner_probe` | 1550 | 8 | 0 | 1 | 7 | `label_contrast_style_jump` |

## Files

- package summary: `package_style_summary.csv`
- sampled pair metrics: `pair_style_sample_metrics.csv`
- worst-case visual sheet: `worst_style_contact_sheet.png`

## Audit Rules

- High risk: label is hard binary/CAD-like, has very weak source-label correspondence, or shape/read errors.
- Medium risk: label contrast/saturation differs strongly from source, but not enough to prove a broken pair.
- Low risk: label keeps a source-like grayscale style under these checks.
- Package is listed as risky when high-risk samples exceed 10% or high+medium samples exceed 25%.
