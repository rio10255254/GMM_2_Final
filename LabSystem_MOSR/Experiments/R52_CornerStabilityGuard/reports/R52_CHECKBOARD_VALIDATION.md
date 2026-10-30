# Lab R52 Corner-Stability Guard Checkboard Validation - 2026-06-15

## Verdict

R52 improves the median corner shift but still raises the large-shift
corner rate. Treat it as directional evidence, not a pass.

## Image Evidence Scope

- Frames checked: 51
- Raw checker corners accepted by the detector: 358
- Case measurements: 5012
- All case folders must preserve the original 51 BMP filenames.

## Corner Geometry Result

| Case | Median corner shift (px) | P75 shift (px) | Corners > 5 px shift | Median local change vs raw | Median edge strength | Harris gain vs raw |
|---|---:|---:|---:|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% | 0.000 | 1.049 | 1.0x |
| Lab R40 tradeoff | 4.243 | 5.000 | 24.581% | 0.068 | 1.361 | 93.4x |
| Lab R46 tradeoff | 4.243 | 8.485 | 48.603% | 0.076 | 1.246 | 114.8x |
| Lab R47 latest E200 | 5.000 | 9.220 | 49.441% | 0.100 | 1.083 | 144.2x |
| Lab R48 best_detail_guarded | 6.708 | 9.220 | 61.453% | 0.128 | 2.910 | 152.7x |
| Lab R49 latest E100 | 9.000 | 9.055 | 85.475% | 0.070 | 1.095 | 3.0x |
| Lab R51 Gaussian best | 3.606 | 9.220 | 37.989% | 0.067 | 1.262 | 104.3x |
| Lab R51 Gaussian latest | 3.606 | 9.220 | 41.061% | 0.068 | 1.272 | 104.4x |
| Lab R51 weak-BADS best | 3.606 | 9.220 | 37.151% | 0.062 | 1.283 | 101.5x |
| Lab R51 weak-BADS latest | 9.220 | 9.899 | 54.469% | 0.054 | 1.229 | 83.0x |
| Lab R51 mixed-PSF best | 2.828 | 9.220 | 36.872% | 0.057 | 1.210 | 89.5x |
| Lab R51 mixed-PSF latest | 2.828 | 9.899 | 41.620% | 0.056 | 1.213 | 86.6x |
| Lab R52 stability best | 3.924 | 9.220 | 49.162% | 0.075 | 0.771 | 144.4x |
| Lab R52 stability latest | 3.606 | 8.485 | 30.447% | 0.095 | 1.098 | 151.4x |

## Pairwise Diagnosis

R52 latest versus Lab R40 tradeoff:

| Result | Count |
|---|---:|
| R52 latest better | 90 |
| Equal | 136 |
| R52 latest worse | 132 |
| R52 latest > 5 px while R40 <= 5 px | 60 |
| R52 latest <= 5 px while R40 > 5 px | 39 |
| R52 latest > 10 px | 28 |
| R40 > 10 px | 17 |

R52 latest versus Lab R51 mixed-PSF best:

| Result | Count |
|---|---:|
| R52 latest better | 126 |
| Equal | 20 |
| R52 latest worse | 212 |
| R52 latest > 5 px while R51 <= 5 px | 77 |
| R52 latest <= 5 px while R51 > 5 px | 100 |
| R52 latest > 10 px | 28 |
| R51 mixed-PSF best > 10 px | 39 |

This explains the mixed result: R52 latest fixes some large-error cases,
but it also creates many new large-error corners where R51 mixed-PSF
was already stable. The focused visual sheet confirms this is a real
corner-localization failure, not just a table artifact.

## R52 Training Coverage Snapshot

| Package | Total pairs | Ring | Shape | Micro | Corner | Formal BADS corner | Gaussian corner | Weak-BADS 0.50 corner |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R52 formal 4000-pair training | 4000 | 550 | 350 | 250 | 400 | 134 | 133 | 133 |
| R52 held-out 700-pair validation | 700 | 0 | 0 | 0 | 100 | 34 | 33 | 33 |
| R51 mixed-PSF source model | 1550 | 550 | 350 | 250 | 400 | 134 | 133 | 133 |
| R51 held-out mixed corner validation | 100 | 0 | 0 | 0 | 100 | 34 | 33 | 33 |

## Package Verification

| Case | Count | Filename identity | Mean absolute change vs raw |
|---|---:|---|---:|
| raw_input | 51 | True | 0.0000 |
| lab_r40_best_tradeoff | 51 | True | 1.3885 |
| lab_r46_best_tradeoff | 51 | True | 1.6573 |
| lab_r47_latest | 51 | True | 1.6246 |
| lab_r48_best_detail_guarded | 51 | True | 1.6560 |
| lab_r49_latest | 51 | True | 5.9453 |
| lab_r51_gaussian_best_tradeoff | 51 | True | 1.3929 |
| lab_r51_gaussian_latest | 51 | True | 1.9820 |
| lab_r51_weak_bads_best_tradeoff | 51 | True | 1.4817 |
| lab_r51_weak_bads_latest | 51 | True | 1.6686 |
| lab_r51_mixed_psf_best_tradeoff | 51 | True | 1.4077 |
| lab_r51_mixed_psf_latest | 51 | True | 1.5898 |
| lab_r52_stability_best_tradeoff | 51 | True | 1.4414 |
| lab_r52_stability_latest | 51 | True | 1.6313 |

## Interpretation Rule

- R52 is a formal Lab stability round, but promotion still depends on real image evidence.
- A promoted result must beat Lab R40 tradeoff on real checkboard corners without increasing large corner errors.
- Training loss and synthetic validation are secondary to the real corner table.

## Artifacts

- Corner metrics table: `../results/archive_retained_20260813/corner_validation/corner_metrics_per_measurement.csv`
- Corner summary table: `../results/archive_retained_20260813/corner_validation/corner_metrics_summary.csv`
- Summary JSON: `../results/archive_retained_20260813/corner_validation/corner_validation_summary.json`
- Visual corner sheet: `../results/archive_retained_20260813/corner_validation/corner_patch_contact_sheet.png`
- Focused corner comparison: `../results/archive_retained_20260813/corner_validation/r52_focus_corner_comparison.png`
- Pairwise comparison JSON: `../results/archive_retained_20260813/corner_validation/r52_pairwise_corner_comparison.json`
- Metric chart: `../results/archive_retained_20260813/corner_validation/corner_metric_summary.png`
- Full reconstruction and GMF-ready image restore entry: `../ARCHIVE_POINTER_R52_20260813.md`
