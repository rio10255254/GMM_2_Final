# R48_RealCornerTransfer

Lab-system real checkboard corner transfer experiment.

This line responds to the R47 finding that simply adding more realistic
boundary images still did not preserve the real `20250605_checkboard` corners.
R48 keeps the reusable R47 package flow, but changes the training target:
it anchors the new data to real Lab checkboard corner failure modes and writes
boundary, centerline, and distance sidecars for every packaged training pair.

## Current Status

Data generation, package validation, formal 200-epoch training, reconstruction,
and real checkboard corner validation are complete.

R48 is a negative result. The model improved on the R48 held-out validation
distribution, but all tested R48 checkpoints made the real `20250605_checkboard`
corner metric worse than the earlier Lab controls. It should not be promoted.

Storage note (2026-08-01): the complete R48 data, training runs and
reconstructions were hash-verified and archived to
`H:\GMM_2_Final_Archive\lab_system\R48_RealCornerTransfer\20260801_full_history`.
This directory retains the canonical reports, manifests, scripts, tests,
training summaries, corner evidence and restore pointers. Read
`ARCHIVE_POINTER_R48_20260801.md` before restoring large payloads.

Validated during this run:

- Clean R48 GT stages generated: 5000 images
- Lab BADS PSF convolved R48 stages generated: 5000 images
- Training package: 6000 pairs
- Held-out real-corner validation package: 1200 pairs
- Geometry sidecars: present for every packaged source image
- Unit tests: passing
- Dry run: passed
- Smoke training: passed, including boundary-geometry activation after warmup
- Formal training: completed to epoch 200 after resume from epoch 120
- Real checkboard reconstruction: 51 frames each for `best_tradeoff`,
  `best_detail_guarded`, and `latest`
- Real corner validation: failed; best R48 median corner shift was `6.708 px`,
  worse than the previous `4.243 px` Lab control

## Data

| Package | Role | Pairs |
|---|---|---:|
| `r48_real_corner_train_6000` | Training mix: ring, shape, micro/defect, real-corner boundary, real-texture corner | 6000 |
| `real_corner_val_unseen` | Held-out real-corner validation package | 1200 |

The new clean GT stages are stored under the Lab `Training_Data/generated/`
tree as stages 53-56, then converted to blurry/noisy inputs through the shared
Lab PSF convolution script.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/r48_real_corner_data.py` | Generate clean R48 real-corner GT, build train/val packages, write geometry sidecars, validate splits, and create previews. |
| `scripts/launch_r48.py` | Launch Lab R48 training from Lab R39/R40 checkpoints with Lab PSF and geometry sidecars mounted. |

## Verification

The R48 tests are in `tests/` and cover:

- deterministic real-corner sample generation
- real-background style usage
- exact train/validation package counts
- train/validation split separation
- geometry sidecar packaging
- launcher dry-run behavior

## Next Step

Use R48 as evidence that simply adding more synthetic real-corner transfer data
with geometry sidecars is not enough. The next redesign should be more tightly
anchored to real checkboard image behavior and should explicitly avoid the
haloed corner shifts seen in the R48 reconstructions.
