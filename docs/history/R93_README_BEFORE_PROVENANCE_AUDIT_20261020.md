# Round 92 — Physical Transition Balanced Scratch

## Purpose

R93 is an independent scratch experiment that corrects the causes identified in R91 while preserving the same local, tile-safe model backbone. It does not load R91, R90, R61, V42, or any other checkpoint.

The experiment targets four coupled goals:

1. accurate and natural contour placement across physical boundary-transition profiles;
2. stable signed displacement and exact tiled reconstruction;
3. visible recovery of genuinely degraded microscopic texture without changing already-clear inputs;
4. exposure robustness that does not dominate the training updates.

## Key corrections relative to R91

- Exposure bundles are sampled at a controlled update share instead of being exhausted every epoch.
- Synthetic contrast spans the very-low-contrast range seen in anonymous aggregate SEM statistics, without mixing degraded sources back toward the target.
- Procedural targets include asymmetric physical transition profiles, with the transition location recorded explicitly.
- Detail restoration and clear-input preservation are measured as separate axes; the unstable adaptive detail controller is removed.
- Validation uses all four exposure views jointly and reports degraded-texture recovery separately from clear-input change.
- If Raw already places a procedural boundary accurately, a continuous non-inferiority term discourages the complete model and the low-frequency branch from making that boundary worse. This is confidence-weighted, not a binary gate, and it does not forbid neutral brightness correction.
- Exposure validation reports all four path regions separately and carries the worst path into the continuous exposure axis, so a strong average cannot hide one failed exposure endpoint.
- Float32 with tile batch one is the primary validation and deployment reference. Bfloat16 is opt-in and diagnostic, and every reconstruction manifest records both precision and tile batch.
- Rare procedurally rendered observations that exceed the model's correction range may receive a source-only global brightness/contrast projection. Original arrays are hash-verified and retained, target pixels are never blended into a source, and the complete package must pass a new full-file audit before training.
- If that global projection cannot satisfy the fixed contract, only the optical and noise parameters may be deterministically resampled inside the same degradation family. Geometry, labels, motion, split and family remain fixed; originals are retained and the whole package is re-audited.
- Training remains 5,000 procedural observations, with more difficult geometry, dense/tile, clean-contour, and motion scenes than R91.

## Isolation

- procedural shapes and labels only;
- labels are rendered at 8x and reduced once by area averaging;
- no SEM or HS100MG pixels, contours, spacing, or structures are training data;
- anonymous aggregate optical scalars may shape nuisance distributions only;
- no checkpoint, resume, teacher, or pseudo-label input exists in the trainer.

## Current state

The R91-informed design revision, smoke validation and full GPU safety/precision benchmark are complete. One independent 80-epoch formal scratch run is explicitly authorized. Its learning rate reaches the former late-training range by epoch 50 and then decays through a restrained 30-epoch tail instead of stretching the aggressive part of training.

## Folder guide

- `config`: the experiment design, safety settings and execution authorization;
- `model`: the reconstruction model itself;
- `training`: the editable training program and loss design;
- `inference`: the standalone full-image and tiled reconstruction program;
- `scripts`: data generation, launch, monitoring and validation entry points;
- `data`: only the audited small smoke set and fixed visual-preview images at setup time;
- `runs`, `weights`, `results`, `reports`: run histories, checkpoints, reconstructions and compact evidence, all kept inside R93.

## Safe execution order

1. Run `scripts/validate_design.py` and `scripts/validate_execution.py --require-implementation`.
2. Run or refresh the measured GPU benchmark after any hardware, model or training-size change; formal launch is refused if the desktop memory reserve is unsafe.
3. Generate and audit the 5,000-observation procedural set and the sealed holdout under the recorded authorization.
4. Start the single authorized 80-epoch scratch run with `scripts/start_formal_training.ps1`.
5. Open `scripts/monitor_training.ps1` for the foreground dashboard, current epoch time and continuously updated remaining-time estimate.

Do not manually enable formal execution by editing one flag in isolation. Authorization, generated-data hashes and the implementation lock must be updated together so the run remains independently traceable.
