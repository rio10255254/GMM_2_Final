# R55 Source-Style Realistic Training Manifest

## Experiment

- ID: R55_SourceStyleRealisticTraining
- Status: completed locally; best_tradeoff passed real checkboard corner gate; external GMF pending
- Created: 2026-06-18
- Scope: LabSystem_MOSR only; source-style data repair validation

## Source Scripts

- `scripts/prepare_r55_geometry.py`
- `scripts/launch_r55.py`
- `scripts/start_r55_formal_training.ps1`

## Data Packages

- Train: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r55_source_style_rebuild\r53_realistic_dataset_calibration\r53_realistic_calibrated_train_6000`
- Validation pool: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r55_source_style_rebuild\r53_realistic_dataset_calibration\r53_realistic_calibrated_val`

## Planned Training

- Scratch run: 50 epochs, batch 16, 4 workers, PSF-forward loss disabled
- Boundary geometry: enabled after preparing sidecars from repaired labels
- Formal log pointer: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R55_SourceStyleRealisticTraining\results\formal_training_logs\latest_formal_training_log.txt`

## Training Runs

- Smoke run: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r55_source_style_r53_scratch_smoke_e001_b002_20260618_002445`
- Formal run: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r55_source_style_r53_scratch_formal_source_style_e050_b016_w04_nophys_20260618_002532`

## Validation

- Checkboard reconstruction outputs: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\r55_reconstruction_outputs`
- GMF-ready best case: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\gmf_cases\lab_r55_source_style_best_tradeoff`
- GMF-ready latest case: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\gmf_cases\lab_r55_source_style_latest`
- Corner validation report: `reports/R55_CHECKBOARD_VALIDATION.md`

## Verification

- `C:\Users\Rio\anaconda3\python.exe -m pytest D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R55_SourceStyleRealisticTraining\tests -q`
- `C:\Users\Rio\anaconda3\python.exe D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R55_SourceStyleRealisticTraining\scripts\prepare_r55_geometry.py`
- `C:\Users\Rio\anaconda3\python.exe D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R55_SourceStyleRealisticTraining\scripts\launch_r55.py --candidate r55_source_style_r53_scratch --num-epoch 50 --dry-run`
