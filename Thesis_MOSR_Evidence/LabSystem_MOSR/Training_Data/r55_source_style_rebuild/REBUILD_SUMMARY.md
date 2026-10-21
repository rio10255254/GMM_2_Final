# Source-Style Training Data Rebuild

- generated_at: `2026-06-17T23:56:34`
- source_training_root: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data`
- unsafe_csv: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20260617_training_data_style_audit_full\unsafe_pair_list.csv`
- rebuilt_packages: `23`
- total_pairs: `51654`
- repaired_pairs: `2186`

## Policy

CAD/old labels are used only to locate boundary bands. Repaired targets keep the source-image grayscale style.

## Packages

| package | pairs | repaired |
|---|---:|---:|
| `foundation_bads_psf` | 11168 | 101 |
| `foundation_gaussian_control` | 3468 | 29 |
| `r39_shape_generalization/shape_val_unseen` | 210 | 2 |
| `r40_microscopy_feature_coverage/micro_val_unseen` | 100 | 5 |
| `r40_microscopy_feature_coverage/r40_micro_capacity_train` | 1300 | 22 |
| `r46_corner_aware_finetune/r46_checkboard_corner_train` | 1550 | 16 |
| `r47_realistic_boundary_generalization/r47_realistic_boundary_train_4000` | 4000 | 49 |
| `r47_realistic_boundary_generalization/realistic_boundary_val_unseen` | 800 | 9 |
| `r48_real_corner_transfer/r48_real_corner_train_6000` | 6000 | 58 |
| `r48_real_corner_transfer/real_corner_val_unseen` | 1200 | 14 |
| `r49_cad_anchor_real_geometry/cad_anchor_val_real` | 120 | 120 |
| `r49_cad_anchor_real_geometry/r49_cad_anchor_train_4000` | 4000 | 439 |
| `r49_cad_anchor_source/test` | 48 | 48 |
| `r49_cad_anchor_source/train` | 408 | 408 |
| `r49_cad_anchor_source/val` | 120 | 120 |
| `r51_blur_source_probe/r51_gaussian_corner_probe` | 1550 | 16 |
| `r51_blur_source_probe/r51_mixed_psf_corner_probe` | 1550 | 16 |
| `r51_blur_source_probe/r51_weak_bads_corner_probe` | 1550 | 16 |
| `r52_corner_stability_guard/r52_corner_stability_train_4000` | 4000 | 32 |
| `r52_corner_stability_guard/r52_corner_stability_val` | 700 | 5 |
| `r53_realistic_dataset_calibration/r53_realistic_calibrated_train_6000` | 6000 | 452 |
| `r53_realistic_dataset_calibration/r53_realistic_calibrated_val` | 1740 | 137 |
| `r54_geometry_root_cause_probe/r54_masked_small_overfit_train` | 72 | 72 |
