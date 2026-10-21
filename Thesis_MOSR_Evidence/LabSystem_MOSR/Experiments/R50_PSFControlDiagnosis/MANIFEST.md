# R50_PSFControlDiagnosis Manifest

Last updated: 2026-06-14

## Identity

| Item | Value |
|---|---|
| Lab line | R50_PSFControlDiagnosis |
| Scope | Lab PSF/degradation diagnostic for real checkboard corner training |
| Status | Completed diagnostic; not a model-training or promotion round |
| Motivation | R48 and R49 failed real Lab checkboard corner validation, so the blur target needed to be checked before another long run |

## Canonical Files

| Item | Status | Location |
|---|---|---|
| R50 diagnostic script | ready | `scripts/psf_control_diagnosis.py` |
| R50 tests | passing | `tests/` |
| R50 results report | completed | `reports/R50_RESULTS.md` |
| Machine-readable summary | completed | `results/psf_control_diagnosis/summary.json` |
| Set-level summary table | completed | `results/psf_control_diagnosis/set_summary.csv` |
| Per-image metric table | completed | `results/psf_control_diagnosis/per_image_metrics.csv` |
| Edge-width chart | completed | `results/psf_control_diagnosis/edge_width_bar_chart.png` |
| Visual contact sheet | completed | `results/psf_control_diagnosis/contact_sheet.png` |
| Weak-BADS alpha 0.50 controls | completed | `results/psf_control_diagnosis/generated_controls/weak_bads_alpha050/stage_48_checkboard_corners/` |
| Weak-BADS alpha 0.75 controls | completed | `results/psf_control_diagnosis/generated_controls/weak_bads_alpha075/stage_48_checkboard_corners/` |

## Verification

| Check | Result |
|---|---|
| Unit tests | 2 passed |
| Real Lab checkboard images measured | 51 |
| Stage-48 clean controls measured | 500 |
| Stage-48 Gaussian controls measured | 500 |
| Stage-48 formal BADS controls measured | 500 |
| Weak-BADS alpha 0.50 controls generated/measured | 500 |
| Weak-BADS alpha 0.75 controls generated/measured | 500 |
| Real median edge-width proxy | 7.0 px |
| Formal BADS median edge-width proxy | 11.0 px |
| Gaussian median edge-width proxy | 9.0 px |
| Weak-BADS alpha 0.50 median edge-width proxy | 7.0 px |
| PSF validation median edge RMSE, Gaussian | 0.093178 |
| PSF validation median edge RMSE, BADS | 0.101790 |

## Handoff

Do not treat R50 as a model candidate. The useful result is the diagnosis: the
formal BADS PSF is not broken, but it is too soft as the single degradation
truth for Lab checkboard corners. Before any next long Lab training run, run a
small controlled training probe that compares Gaussian, weakened-BADS, and
mixed-PSF targets against the real checkboard-corner gate.

