# R54 Geometry Root-Cause Probe

## Hypothesis

The repeated Lab checkboard failures are not mainly caused by insufficient
training volume. The immediate failure mode is that reconstruction changes real
corner geometry, so the next step must isolate geometry preservation before any
long run.

## Design

R54 started as a diagnosis round, then ran a constrained masked small-overfit
probe. It reuses the R53 real-checkboard corner validation summary and the
20260613 strict-rectangle CAD-reference data.

The probe checks:

- whether raw input is still the best geometry reference;
- whether reconstruction itself raises large real-corner errors;
- whether the strict-rectangle CAD references are usable for a masked small
  overfit probe;
- whether a local CAD-edge fit transfers safely to the real Lab checkboard
  sequence.

## Result

R54 supports the reconstruction-damage hypothesis. The corrected edge-band
small-overfit probe passes on the masked CAD package, but fails on the real
Lab checkboard sequence. It should not be used as a Lab model.

Key numbers:

| Item | Result |
|---|---:|
| Raw input corners >5 px | 1.676% |
| Best reconstruction corners >5 px | 24.581% |
| R53 latest corners >5 px | 58.939% |
| Valid CAD-reference pairs | 36 |
| High-quality probe pairs | 36 |
| Median reliable-mask coverage | 0.0161 |
| Masked CAD package input inside MAE | 61.145 |
| R54 epoch20 masked CAD inside MAE | 9.268 |
| R54 epoch20 real-checkboard median corner shift | 9.220 px |
| R54 epoch20 real-checkboard corners >5 px | 60.056% |

The CAD references are usable as local masked supervision only. They should not
be treated as full-frame GT, and the current R54 edge-band checkpoint should not
be continued as a formal training candidate.

## Artifacts

- Main report: `reports/R54_DIAGNOSTIC.md`
- Masked small-probe report: `reports/R54_MASKED_SMALL_PROBE.md`
- Real checkboard validation report: `reports/R54_CHECKBOARD_VALIDATION.md`
- Diagnosis JSON: `results/root_cause_probe/r54_root_cause_diagnosis.json`
- Selected small-probe pairs: `results/root_cause_probe/r54_small_overfit_probe_pairs.csv`
- Visual overlay sheet: `results/root_cause_probe/r54_small_probe_overlays.png`
- R54 GMF-ready folder: `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r54_edgeband_epoch020`

## Verification

```powershell
C:\Users\Rio\anaconda3\python.exe -m pytest Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/tests -q
C:\Users\Rio\anaconda3\python.exe -u Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/scripts/r54_geometry_root_cause_probe.py
C:\Users\Rio\anaconda3\python.exe -u Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/scripts/r54_masked_overfit_probe.py validate --strict
C:\Users\Rio\anaconda3\python.exe -u Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/scripts/run_r54_checkboard_reconstruction.py --dry-run
C:\Users\Rio\anaconda3\python.exe -u Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/validate_checkboard_corner_geometry_r54.py
```
