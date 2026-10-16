# R50 PSF Control Diagnosis

## Verdict

The formal BADS PSF is usable, but it should not be treated as the only blur truth for the Lab checkboard corner task. In this diagnostic, weakened BADS best matches the real edge-width proxy, while the Gaussian control is the best combined width/edge-strength compromise. The formal BADS input is the widest/softest of the realistic controls.

## Edge-Width Comparison

| Set | Images | Median edge width (px) | Gap vs real (px) | Median grad p99 | Rank score |
|---|---:|---:|---:|---:|---:|
| real_raw_checkboard | 51 | 7.000 | 0.000 | 0.025495 | 0.000 |
| clean_synthetic_stage48 | 500 | 0.500 | 6.500 | 0.485862 | 18.009 |
| gaussian_control_stage48 | 500 | 9.000 | 2.000 | 0.109669 | 4.104 |
| weak_bads_alpha050 | 500 | 7.000 | 0.000 | 0.290995 | 6.637 |
| weak_bads_alpha075 | 500 | 9.000 | 2.000 | 0.189798 | 6.108 |
| formal_bads_stage48 | 500 | 11.000 | 4.000 | 0.090792 | 5.632 |

## PSF Calibration Check

| Forward model | Median edge RMSE |
|---|---:|
| sharp_gt | 0.212012 |
| global_gaussian | 0.093178 |
| bads_fitted | 0.101790 |

## Interpretation

- Width-only best match: `weak_bads_alpha050`.
- Combined width/edge-strength best match: `gaussian_control_stage48`.
- Formal BADS edge width is `11.0 px` versus real `7.0 px`.
- BADS PSF is not broken, but it is not the safest single blur truth for checkboard corners.
- The Lab model failures are still more consistent with target/degradation mismatch than raw model incapacity.
- The next training probe should compare Gaussian / weakened-BADS / mixed-PSF data before any long formal run.

## Generated Weak-BADS Sets

- `weak_bads_alpha050`: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R50_PSFControlDiagnosis\results\psf_control_diagnosis\generated_controls\weak_bads_alpha050\stage_48_checkboard_corners`
- `weak_bads_alpha075`: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R50_PSFControlDiagnosis\results\psf_control_diagnosis\generated_controls\weak_bads_alpha075\stage_48_checkboard_corners`

## Artifacts

- `summary.json`: machine-readable summary
- `set_summary.csv`: compact set-level table
- `per_image_metrics.csv`: per-image measurements
- `edge_width_bar_chart.png`: visual ranking
- `contact_sheet.png`: source preview sheet
