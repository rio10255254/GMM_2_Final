# R47_RealisticBoundaryGeneralization

Lab-system realistic boundary/generalization data expansion.

This line responds to the R46 finding that ideal synthetic checkboard/corner
coverage was not enough to transfer to the real Lab checkboard sequence. R47
keeps the existing ring, shape, and microstructure coverage, then adds a larger
and more realistic boundary set built from hard corners, intersections, PSF
stress cases, and real Lab checkboard background style.

## Current Status

Data generation, package validation, and the first full 200-epoch R47 training
run are complete. Both R47 checkpoints were then reconstructed on the real
`20250605_checkboard` Lab sequence and checked with the existing
corner-geometry workflow.

- epoch 33 `best_tradeoff.pth.tar`: trainer-selected conservative checkpoint
- epoch 200 `latest.pth.tar`: final checkpoint with stronger validation metrics
  but more late boundary-smoothing guard warnings

The real checkboard result is negative. Epoch 200 is less bad than epoch 33,
but neither checkpoint fixes the rounded-corner problem, and R47 should not be
promoted as a usable Lab reconstruction model.

## Data

| Package | Role | Pairs |
|---|---|---:|
| `r47_realistic_boundary_train_4000` | Training mix: ring, shape, micro/defect, synthetic hard-boundary, real-background boundary | 4000 |
| `realistic_boundary_val_unseen` | Held-out realistic boundary validation | 800 |

The new clean GT stages are stored under the Lab `Training_Data/generated/`
tree as stages 49-52, then converted to blurry/noisy inputs through the shared
Lab PSF convolution script.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/r47_realistic_boundary_data.py` | Generate clean R47 boundary GT, build train/val packages, validate splits, and create previews. |

## Results

The data report is in:

`Training_Data/reports/LAB_R47_REALISTIC_BOUNDARY_DATA_20260612.md`

The training result report is in:

`Experiments/R47_RealisticBoundaryGeneralization/reports/R47_RESULTS_20260613.md`

The real checkboard validation report is in:

`Experiments/R47_RealisticBoundaryGeneralization/reports/R47_CHECKBOARD_VALIDATION_20260613.md`

The generated previews are:

- `Training_Data/reports/r47_realistic_boundary_clean_preview.png`
- `Training_Data/reports/r47_realistic_boundary_convolved_preview.png`

## Next Step

Do not continue R47 by only adding epochs. The next useful step is to redesign
the boundary training and checkpoint-selection logic around real Lab corner
preservation, then rerun the same real checkboard validation. The prepared R47
GMF case folders can still be scored externally, but the current corner result
is already a failed validation.
