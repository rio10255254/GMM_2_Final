# R56 Label Core Repair Summary

- generated_at: `2026-06-18T10:09:32`
- output_root: `LabSystem_MOSR/Training_Data/r56_label_core_repair/r53_realistic_dataset_calibration`
- total_pairs: `7740`
- core_repaired_pairs: `589`
- grad_ratio_threshold: `1.5`

## Policy

Keep the real source grayscale style, but rebuild weak label edge cores from source-derived local intensities.
Old CAD or label images locate edge bands only; they are not copied back as black/white fills.

## Packages

| package | pairs | core repaired | min repaired grad ratio |
|---|---:|---:|---:|
| `r53_realistic_calibrated_train_6000` | 6000 | 452 | 1.303 |
| `r53_realistic_calibrated_val` | 1740 | 137 | 2.932 |
