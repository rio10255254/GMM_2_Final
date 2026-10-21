# R93 Manifest

## Identity

- Round: `R93`
- Name: `PhysicalTransitionBalancedScratch`
- Role: independent research candidate; no baseline change
- Parent evidence: R91 root-cause analysis only
- Checkpoint inheritance: prohibited

## Reproducibility contract

- Master seed: `920041`
- Formal scale: `1,250 scenes x 4 observations = 5,000 observations`
- Label construction: `8x supersampling -> one area reduction`
- Formal runs: one explicitly authorized independent 80-epoch run
- Training selection: procedural validation only
- Primary validation and deployment reference: float32, tile batch one; bfloat16 is diagnostic only
- Exposure reporting: four predeclared path regions plus the continuous worst-path contour ratio
- Raw protection: continuous procedural boundary non-inferiority, never a binary gate
- Recoverability correction: only a traceable global source photometric projection, with original-array backup and complete re-hash; no target-pixel mixing
- Unprojectable synthetic observation: deterministic full rerender inside the same degradation family only, with exact backup and complete re-hash
- Real microscope images: fixed visual previews only, never loss, selection, or training input

## Main entry points

- Dataset builder: `scripts/generate_dataset.py`
- Training launcher: `scripts/launch_r93.py`
- Training program: `training/train_r93.py`
- Reconstruction: `inference/reconstruct.py`
- Foreground monitor: `scripts/monitor_training.ps1`
- Design validation: `scripts/validate_design.py`
- Execution validation: `scripts/validate_execution.py`

## Storage contract

Bulk data, runs, results, and weights remain experiment-local and outside Git. No R91 payload is copied into R93. Old experiment payloads may be archived only through a hash-verified, reversible operation.
