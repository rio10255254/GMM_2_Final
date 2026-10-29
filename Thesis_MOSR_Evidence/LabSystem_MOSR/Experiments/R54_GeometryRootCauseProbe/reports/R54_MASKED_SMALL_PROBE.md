# R54 Masked Small-Overfit Probe

## Verdict

R54 confirms a split result:

- The model can fit the selected CAD edge supervision locally.
- That local fit does not transfer safely to the real `20250605_checkboard`
  sequence.

R54 is therefore root-cause evidence, not a usable Lab model.

## What Changed After the First Attempt

The first masked package was invalid for the intended question because the
trusted mask mostly covered flat interior areas and excluded CAD boundaries. It
made the model whiten local regions, so the apparent loss improvement was not
evidence of learning real edges.

The corrected package adds a CAD edge band to the trusted mask. This makes every
training patch contain actual CAD boundary evidence.

## Masked CAD Package Check

| Item | Result |
|---|---:|
| Training pairs | 72 |
| Missing files | 0 |
| Outside-mask label mismatch pixels | 0 |
| Patches with changed supervised pixels | 72 |
| Patches with zero CAD-edge content | 0 |
| Median trusted-mask ratio | 0.6545 |
| Median CAD-edge ratio | 0.0231 |

## Small-Package Reconstruction Result

| Case | Inside MAE to label | Improvement vs input | Outside drift |
|---|---:|---:|---:|
| Input source | 61.145 | 0.000% | 0.000 |
| Lab R40 base | 50.053 | 18.182% | 5.914 |
| R54 edge-band epoch5 | 13.765 | 77.500% | 4.428 |
| R54 edge-band epoch10 | 12.194 | 80.058% | 6.242 |
| R54 edge-band epoch20 | 9.268 | 84.839% | 7.174 |

This is a real local-learning signal: epoch20 is much closer to the CAD label
inside the supervised mask than either the source image or Lab R40.

## Real Checkboard Gate

The same epoch20 checkpoint was reconstructed on the real Lab
`20250605_checkboard` sequence and failed the real-corner gate.

| Case | Median corner shift | Corners > 5 px | Local change vs raw |
|---|---:|---:|---:|
| Raw input | 1.414 px | 1.676% | 0.000 |
| Lab R40 tradeoff | 4.243 px | 24.581% | 0.068 |
| R53 realistic best | 3.606 px | 40.782% | 0.059 |
| R53 realistic latest | 9.220 px | 58.939% | 0.075 |
| R54 edge-band epoch20 | 9.220 px | 60.056% | 0.080 |

R54 is worse than Lab R40 on the real sequence. It also changes the real images
much more strongly than the other reconstruction cases.

## Interpretation

The useful lesson is precise: the model is not simply too weak to learn CAD
edges. It can learn them in a small masked package. The failure is that this
kind of small local adaptation changes the real image too aggressively and does
not preserve real checkboard corner geometry.

The next experiment should therefore target constrained real-domain adaptation:
improve CAD-edge regions while explicitly preventing output drift and real
corner displacement. Another long generic-data run or a direct continuation
from this R54 edge-band checkpoint is not justified.

## Artifacts

- Masked package: `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r54_geometry_root_cause_probe/r54_masked_small_overfit_train`
- Small-probe eval summary: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/results/masked_overfit_probe/r54_edgeband_eval_summary.csv`
- Small-probe visual sheet: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/results/masked_overfit_probe/r54_edgeband_eval_contact_sheet.png`
- Real checkboard validation report: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/reports/R54_CHECKBOARD_VALIDATION.md`
- Real checkboard corner metrics: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r54_20260616/corner_metrics_summary.csv`
- R54 GMF-ready image folder: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r54_edgeband_epoch020`
