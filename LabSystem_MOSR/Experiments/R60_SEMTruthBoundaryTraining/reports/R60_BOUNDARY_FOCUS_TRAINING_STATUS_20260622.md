# R60 Boundary-Focus Training Status - 2026-06-22

## Current Finding

The boundary problem is now traced to both data validation and training objective design.
After grouped + stratified splitting removed repeated-crop leakage, the old R60 setting no longer passed the per-class CD gate.
A boundary-focused training candidate was then added and tested without any post-hoc sample calibration.

## Data Repair

- Repeated real microscope crops are now grouped before train/validation split.
- Validation is stratified by source group and feature.
- Real-data split check:
  - default validation split: 1676 train, 200 validation, 0 group overlap.
  - small validation split: 1824 train, 52 validation, 0 group overlap.
  - validation covers real/pillar, real/via, anchor/pillar, anchor/via.

## Model/Training Change Tested

Candidate: `r60_semtruth_boundary_focus`

- Uses the same R60 SEM-truth data package.
- Increases SEM boundary/centerline/distance supervision.
- Disables sequence auxiliary training for this CD-focused pass.
- Keeps PSF-forward training disabled.
- Keeps selection based on post-reconstruction CD against SEM, not internal best-tradeoff.

## CD Results

| Run | Checkpoint | Mean abs radius error | Via abs error | Pillar abs error | Gate |
|---|---|---:|---:|---:|---|
| Original image | source | 38.59 nm | 66.13 nm | 11.04 nm | reference |
| Grouped+stratified old R60 | e004 mtb064 latest | 26.54 nm | 39.59 nm | 13.48 nm | fail |
| Boundary-focus | e004 mtb064 latest | 7.81 nm | 12.40 nm | 3.21 nm | pass |
| Boundary-focus | e008 mtb064 epoch_005 | 4.52 nm | 3.23 nm | 5.81 nm | pass |
| Boundary-focus | e008 mtb064 epoch_008/latest | 8.01 nm | 4.59 nm | 11.44 nm | fail |
| Boundary-focus | e002 mtb256 latest | 9.96 nm | 16.33 nm | 3.58 nm | pass |
| Boundary-focus | e003 mtb256 latest | 11.71 nm | 13.58 nm | 9.84 nm | pass |
| Boundary-focus | e004 mtb256 latest | 16.27 nm | 22.53 nm | 10.00 nm | pass |
| Boundary-focus | e005 mtb256 latest | 17.98 nm | 19.64 nm | 16.32 nm | fail |

## Interpretation

The model can now learn accurate boundaries when training is boundary-focused and stopped by CD.
However, the pillar error drifts back upward with longer training.
This confirms that ordinary training loss is still not a safe stopping rule.

The best measured checkpoint in this pass is:

- run: `boundary_focus_e008_mtb064_20260622_epochs`
- checkpoint: `epoch_005`
- mean abs radius error: 4.52 nm
- via abs error: 3.23 nm
- pillar abs error: 5.81 nm

For a larger-batch safer candidate, use:

- run: `boundary_focus_e003_mtb256_20260622`
- checkpoint: `latest`
- mean abs radius error: 11.71 nm
- via abs error: 13.58 nm
- pillar abs error: 9.84 nm

## Next Gate

Do not promote a checkpoint by internal validation loss alone.
Promote only checkpoints that pass the external SEM CD gate for both via and pillar.
