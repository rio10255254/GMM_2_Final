# R54 Geometry Root-Cause Probe Manifest

- ID: R54_GeometryRootCauseProbe
- Status: completed diagnostic + masked small-overfit probe; real checkboard gate failed
- Role: Lab-system root-cause probe; not a usable Lab model
- Branch note: created in the current thesis workspace; this working tree was
  already dirty, so no branch switch was performed in-session

## Inputs

- R53 real-checkboard corner summary:
  `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r53_20260616/corner_metrics_summary.csv`
- 20260613 strict-rectangle CAD references:
  `LabSystem_MOSR/Reconstruct_Progress/20260613_checkboard_cad_reference_strict_rect`

## Scripts

- Root-cause probe: `scripts/r54_geometry_root_cause_probe.py`
- Masked CAD package builder/evaluator: `scripts/r54_masked_overfit_probe.py`
- Masked-overfit launcher: `scripts/launch_r54_masked_overfit.py`
- Masked package reconstruction evaluator: `scripts/r54_masked_overfit_eval.py`
- Real checkboard reconstruction runner: `scripts/run_r54_checkboard_reconstruction.py`
- Real checkboard corner validator: `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/validate_checkboard_corner_geometry_r54.py`

## Reports

- Main diagnosis report: `reports/R54_DIAGNOSTIC.md`
- Masked small-probe report: `reports/R54_MASKED_SMALL_PROBE.md`
- Real checkboard validation report: `reports/R54_CHECKBOARD_VALIDATION.md`

## Results

- Diagnosis JSON: `results/root_cause_probe/r54_root_cause_diagnosis.json`
- Hypothesis table: `results/root_cause_probe/r54_hypothesis_table.csv`
- Selected masked small-probe pairs: `results/root_cause_probe/r54_small_overfit_probe_pairs.csv`
- Overlay contact sheet: `results/root_cause_probe/r54_small_probe_overlays.png`
- Masked small-overfit package: `../../Training_Data/r54_geometry_root_cause_probe/r54_masked_small_overfit_train`
- Edge-band package preview: `results/masked_overfit_probe/r54_masked_overfit_edgeband_preview.png`
- Edge-band small-probe eval summary: `results/masked_overfit_probe/r54_edgeband_eval_summary.csv`
- Edge-band small-probe contact sheet: `results/masked_overfit_probe/r54_edgeband_eval_contact_sheet.png`
- Edge-band training run: `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r54_masked_overfit_from_r40_edgeband_e020_20260616_224650`
- Real checkboard reconstruction output: `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/r54_reconstruction_outputs`
- R54 GMF-ready case folder: `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r54_edgeband_epoch020`
- R54 real checkboard validation artifacts: `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r54_20260616`

## Verdict

R54 confirms that the model can learn local CAD edge supervision, but the
edge-band epoch20 checkpoint fails on the real Lab checkboard sequence. The
masked small-probe is useful evidence, not a deployable model. Do not continue
from this R54 edge-band checkpoint as a formal Lab training candidate.

## Verification

```powershell
C:\Users\Rio\anaconda3\python.exe -m pytest LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/tests -q
C:\Users\Rio\anaconda3\python.exe -u LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/scripts/r54_geometry_root_cause_probe.py
C:\Users\Rio\anaconda3\python.exe -u LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/scripts/r54_masked_overfit_probe.py validate --strict
C:\Users\Rio\anaconda3\python.exe -u LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/scripts/run_r54_checkboard_reconstruction.py --dry-run
C:\Users\Rio\anaconda3\python.exe -u LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/validate_checkboard_corner_geometry_r54.py
```
