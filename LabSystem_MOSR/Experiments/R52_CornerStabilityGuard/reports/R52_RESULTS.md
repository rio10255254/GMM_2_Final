# R52 Corner-Stability Guard Results

Date: 2026-06-15

## Status

R52 formal 100-epoch training completed, but R52 is not promoted.

The best usable checkpoint from this round is still not stable enough on real
Lab checkboard corners. R52 improves some typical corner locations, but it
still creates too many large corner shifts.

## What Completed

| Component | Result |
|---|---:|
| Formal train package | 4000 pairs |
| Held-out validation package | 700 pairs |
| Geometry sidecars in train package | 4000 |
| Geometry sidecars in validation package | 700 |
| Formal training | 100 epochs completed |
| Real checkboard reconstruction | 51 frames x 2 checkpoints |
| R52 tests | 6 passed |
| Real corner gate | failed |

## Formal Training

| Item | Value |
|---|---|
| Start checkpoint | R51 mixed-PSF `best_tradeoff` |
| Training length | 100 epochs |
| Run history | Full copy in the H-drive archive; logs, curves and three representative checkpoints remain in `../results/archive_retained_20260813/formal_run_evidence/` |
| Internal best epoch | 23 |
| Final validation PSNR / SSIM | 27.12 / 0.9495 |
| Final status note | detail guard kept firing; not sufficient for promotion |

The internal best checkpoint stayed at epoch 23. The epoch-100 `latest`
checkpoint looked better than the early best on the real corner gate, but it
still did not pass.

## Real Checkboard Corner Validation

| Case | Median shift (px) | P75 shift (px) | Corners > 5 px |
|---|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% |
| Lab R40 control | 4.243 | 5.000 | 24.581% |
| R51 mixed-PSF best | 2.828 | 9.220 | 36.872% |
| R52 stability best | 3.924 | 9.220 | 49.162% |
| R52 stability latest | 3.606 | 8.485 | 30.447% |

Gate rule: R52 must beat R40 on median shift and must not increase the
large-shift corner rate.

Result: R52 latest improves the median shift compared with R40, but the
large-shift rate is still worse than R40. Therefore it fails the gate.

## Pairwise Diagnosis

R52 latest versus R40:

| Result | Count |
|---|---:|
| R52 better | 90 |
| Equal | 136 |
| R52 worse | 132 |
| R52 > 5 px while R40 <= 5 px | 60 |
| R52 <= 5 px while R40 > 5 px | 39 |

R52 latest versus R51 mixed-PSF best:

| Result | Count |
|---|---:|
| R52 better | 126 |
| Equal | 20 |
| R52 worse | 212 |
| R52 > 5 px while R51 <= 5 px | 77 |
| R52 <= 5 px while R51 > 5 px | 100 |

Interpretation: R52 reduces some R51 large-error cases, but also breaks many
corners that R51 handled correctly. This is a stability failure, not a clean
model improvement.

## External GMF Status

The two R52 reconstructed image folders have been synced for external GMF and
are preserved in the H-drive archive:

- `lab_r52_stability_best_tradeoff`
- `lab_r52_stability_latest`

No R52 external GMF score text files were present at the time of this report.
Restore the two complete 51-frame folders through
`../ARCHIVE_POINTER_R52_20260813.md` before external GMF follow-up.

## Canonical Artifacts

- Real checkboard validation report: `R52_CHECKBOARD_VALIDATION.md`
- Corner metrics folder: `../results/archive_retained_20260813/corner_validation/`
- Focused corner comparison: `../results/archive_retained_20260813/corner_validation/r52_focus_corner_comparison.png`
- Gate outputs: `../results/r52_latest_corner_gate.json`, `../results/r52_best_tradeoff_corner_gate.json`
- Full-history restore entry: `../ARCHIVE_POINTER_R52_20260813.md`

## Verdict

R52 is useful evidence but not a usable Lab model. The next round should not
only add more corner data. It needs a stronger way to stop the model from
moving the corner peak to the wrong nearby edge.
