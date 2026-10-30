# R52_CornerStabilityGuard

Lab-system formal corner-stability run.

R52 keeps the useful R51 mixed-PSF direction, then adds R48 real-corner
stability data and geometry sidecars so the long run is not judged by synthetic
loss alone.

## Current Status

Started on 2026-06-14 and completed on 2026-06-15.

Validated so far:

- Unit tests: passing
- Formal train package: 4000 pairs
- Held-out validation package: 700 pairs
- Train/validation split check: passed
- Training dry-run: passed
- Smoke training: passed
- Formal 100-epoch training: completed from the R51 mixed-PSF `best_tradeoff`
  checkpoint
- Real `20250605_checkboard` reconstruction: completed for `best_tradeoff`
  and `latest`
- Real corner stability gate: failed

R52 is not a promoted model. It improved some typical corner measurements, but
it still produced too many large-shift corners on the real Lab checkboard
sequence.

## Historical Archive

On 2026-08-13, the complete R52 data, training and reconstruction history was
copied to `H:\GMM_2_Final_Archive\lab_system\R52_CornerStabilityGuard\20260813_full_history`.
All eight snapshot sources, including the final experiment context, passed
file-by-file SHA-256 verification. D retains the
canonical reports, code, tests and a compact evidence package at
`results/archive_retained_20260813/`. Read `ARCHIVE_POINTER_R52_20260813.md`
before restoring or rerunning the historical package. After R95 completed and
was verified, the seven exact large D-drive sources were removed on 2026-08-24;
all eight H-drive manifests passed again, and the final experiment-context
manifest was rebuilt and verified. See `ARCHIVE_EXECUTION_R52_20260824.json`.

## Data

| Package | Role | Pairs |
|---|---|---:|
| `r52_corner_stability_train_4000` | R51 mixed-PSF core plus R48 real-corner stability sources | 4000 |
| `r52_corner_stability_val` | Held-out mixed-PSF and real-corner validation set | 700 |

The formal training package contains:

- 550 ring pairs
- 350 shape pairs
- 250 microscopy pairs
- 400 mixed-PSF checkboard-corner pairs
- 1800 real-corner / lattice / PSF-stress boundary pairs
- 650 real-texture corner pairs

Every packaged pair has geometry sidecars.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/r52_corner_stability_data.py` | Build and validate the R52 training and validation packages. |
| `scripts/launch_r52.py` | Launch R52 training from R51 mixed-PSF or R40 checkpoints. |
| `scripts/r52_corner_gate.py` | Apply the real-checkboard corner stability gate after reconstruction. |
| `scripts/run_r52_checkboard_reconstruction.py` | Reconstruct the real `20250605_checkboard` sequence after training finishes. |

## Verification

The R52 tests are in `tests/` and cover:

- 4000-pair formal package composition
- Mixed-PSF corner-source balance
- Held-out split isolation
- Geometry sidecar generation
- Launcher dry-run behavior
- Corner gate pass/fail logic

## Next Step

Use R52 as failure evidence for the next design. The next round should keep the
mixed-PSF direction only if it also adds a stronger corner-localization guard,
because R52 reduced some large R51 errors but created too many new large corner
shifts.

Archiving does not reopen this research line and does not change the failed-gate
verdict.
