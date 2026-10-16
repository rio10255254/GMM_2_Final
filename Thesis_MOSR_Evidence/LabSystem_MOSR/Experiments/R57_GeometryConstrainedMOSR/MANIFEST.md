# R57 Geometry-Constrained MOSR Manifest

## Experiment

- ID: R57_GeometryConstrainedMOSR
- Status: pilot implementation and short training completed; CD gate not yet passed
- Created: 2026-06-20
- Scope: LabSystem_MOSR, HS-100MG / Basler ace acA2040-120um geometry-constrained fine-tune

## Source Scripts

- `scripts/prepare_r57_geometry_dataset.py`
- `scripts/launch_r57.py`
- `scripts/validate_r57_cd_gate.py`

## Planned Data

- Base package: R55 source-style repaired R53 training package.
- Generated anchor package root: `LabSystem_MOSR/Training_Data/r57_geometry_constrained/hs100mg_basler_anchor`
- Mixed train profile: `r57_hs100mg_r55_finetune_train`
- Default generated anchor count: 2048

## Model Strategy

- Start from R55 best_tradeoff by default.
- Keep the same model architecture for the first R57 run.
- Disable PSF-forward loss by default.
- Increase geometry supervision near label boundaries.
- Keep sequence displacement supervision active.
- Use the 100MG SEM-referenced CD gate for model selection.
- Use `--anchor-focus` for short calibration runs when the mixed package does
  not expose enough 100MG anchor samples.
- R57.1 asymmetric CD anchors are available for investigation, but the completed
  aligned pilot failed the CD gate and is not adopted.

## Basler / 100MG Reference

- Camera: Basler ace acA2040-120um
- Camera pixel size: 3.45 um
- Objective: 50x
- Object-plane scale used for CD gate: 69 nm/px
- SEM radius references from current 100MG sample:
  - pillar: 1321.882 nm
  - via: 1641.999 nm

## Verification Commands

```powershell
C:\Users\Rio\anaconda3\python.exe -m pytest D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R57_GeometryConstrainedMOSR\tests -q
```

```powershell
C:\Users\Rio\anaconda3\python.exe -u D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R57_GeometryConstrainedMOSR\scripts\launch_r57.py --candidate r57_geom_cd_anchor_finetune --dry-run
```

```powershell
C:\Users\Rio\anaconda3\python.exe -u D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R57_GeometryConstrainedMOSR\scripts\validate_r57_cd_gate.py --summary-csv D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20260618_100MG_user_recon\cd_measurement_20260620_basler_ace\cd_measurement_summary_basler_50x.csv --candidate-image "PSF關" --reference-image "原圖"
```

## Pilot Runs

- Smoke run: completed; confirmed R57 data, R55 checkpoint loading, geometry loss, and sequence loss can run.
- Mixed pilot: completed; CD gate failed.
- Anchor-focus pilot: completed; improved R55 CD error but still failed against the original image.
- Anchor-focus then mixed recovery: completed; worse than anchor-focus latest on the 100MG CD gate.
- R57.1 asymmetric CD aligned pilot: completed; worse than original image and
  worse than R57 anchor-focus latest on the 100MG CD gate.

## Current Best Exploratory Candidate

- Candidate: anchor-focus latest checkpoint
- Training run: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r57_geom_cd_anchor_finetune_anchor_focus_e006_b004_mtb080_20260620_153625`
- Reconstruction: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20260618_100MG_user_recon\reconstruct_progress_latest_in_20260618_100MG_20260620_153625\r57_anchor_focus_e006_b004_mtb080_latest_weakpsf_off`
- CD report: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20260618_100MG_user_recon\cd_measurement_20260620_r57_anchor_focus_latest`
- Gate report: `reports/r57_anchor_focus_latest_cd_gate.json`
- Adoption status: not adopted; still worse than original-image CD error.

## Rejected R57.1 Candidate

- Candidate: asymmetric CD latest checkpoint
- Training run: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r57_1_asym_cd_anchor_finetune_asym_cd_aligned_e004_b004_mtb120_lr3e6_20260620_163628`
- Reconstruction: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20260618_100MG_user_recon\reconstruct_progress_latest_in_20260618_100MG_20260620_163628\r57_1_asym_cd_aligned_e004_latest_weakpsf_off`
- CD report: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20260618_100MG_user_recon\cd_measurement_20260620_r57_1_asym_cd_aligned_latest`
- Gate report: `reports/r57_1_asym_cd_aligned_latest_cd_gate.json`
- Adoption status: rejected; the direct full-radius asymmetric CD correction
  overcorrected both via and pillar boundaries.
