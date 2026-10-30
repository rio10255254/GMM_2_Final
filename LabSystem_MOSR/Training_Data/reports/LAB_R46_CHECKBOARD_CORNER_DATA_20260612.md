# Lab R46 Checkboard/Corner Data - 2026-06-12

## What Was Built

This round adds a Lab-specific checkboard/right-angle corner data family for the
20250605 checkboard reconstruction problem.

It does not replace the stage 1-33 foundation. It extends it with one new Lab
stage and one R46 training package.

## Outputs

| Output | Count |
|---|---:|
| Clean GT: `stage_48_checkboard_corners` | 500 images |
| Lab BADS-PSF convolved inputs | 500 images |
| Gaussian-control convolved inputs | 500 images |
| R46 train package | 1550 pairs |
| R46 held-out checkboard validation package | 100 pairs |

## Training Package Mix

| Role | Pairs |
|---|---:|
| Ring replay | 550 |
| R39 shape replay | 350 |
| R40 micro replay | 250 |
| New checkboard/corner data | 400 |

The held-out validation package contains 100 checkboard/corner pairs that are
not included in the training package.

## Sanity Checks

| Check | Result |
|---|---|
| Clean/BADS/Gaussian counts | 500 / 500 / 500 |
| Image size and dtype | 512x512, uint8 |
| Clean GT vs BADS identical? | no |
| Clean GT vs Gaussian identical? | no |
| BADS vs Gaussian identical? | no |
| Train/validation split | disjoint |
| Package src/lbl sample check | all sampled paths exist |
| Corner preview | `r46_checkboard_corner_preview.png` |
| Summary JSON | `r46_checkboard_corner_data_summary.json` |

## Trainer Compatibility

The shared trainer recognizes existing data roles by path prefix. The new clean
stage remains named `stage_48_checkboard_corners`, but the materialized package
places those samples under a boundary-compatible package path. This lets the
existing trainer run without changing the shared model code.

## Launcher Verification

The new R46 Lab launcher passed dry-run and one smoke training pass:

| Check | Result |
|---|---|
| Dry-run | passed |
| Smoke training | passed |
| Smoke scope | 1 epoch, 1 train batch, validation ratio 0.01 |
| Base checkpoint | Lab R39 latest |
| Data package | `r46_checkboard_corner_train` |

Smoke run folder:

`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_111237/`

## Next Decision

The data and launcher are ready for a formal R46 Lab fine-tune. This should be
treated as the next experiment, not as a completed model result yet. The formal
run should be followed by the existing checkboard corner geometry validation
and the 20250605 checkboard reconstruction/GMF analysis.
