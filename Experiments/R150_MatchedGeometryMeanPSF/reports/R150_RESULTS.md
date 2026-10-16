# R150 Training Results

## Completion

- One formal scratch run completed 8,192/8,192 contiguous updates.
- Final checkpoint SHA-256: `1ce02e2c7f25bc88677212d02ee7116bef4dc61c45558f0dc135cee3e2d31e27`.
- Source, data, PSF, checkpoint identity and inference readiness passed.
- No inherited model or short-test weight was used.
- Real 930-frame validation is pending; this report does not claim real PI or SEM improvement.

## Fixed generated results

The formal dev mean decreased monotonically from 7.811771 to 1.744712, a 77.67% reduction. The independent fixed test mean was 1.656627. The final three 512-update improvements were 0.02352, 0.01462 and 0.00821, so the run was still improving slowly without a dev reversal.

## Fair frozen comparison with R148v2

Both final checkpoints were recomputed on the exact R150 dev and test inputs, noise, mean-PSF operator and objective.

| Fixed test scope | Parents | R148v2 | R150 | R150 change |
|---|---:|---:|---:|---:|
| All | 128 | 1.770893 | 1.656627 | -6.45% |
| New matched circles | 16 | 2.045834 | 1.762404 | -13.85% |
| Unchanged scenes | 112 | 1.731616 | 1.641516 | -5.20% |

On the 16 matched-circle test parents, local boundary error decreased 16.58%. The magnitude of the signed boundary displacement decreased 58.27%, from 0.00479 px to 0.00200 px. On all 128 test parents, local boundary error decreased 14.28%.

The unchanged 112 parents also improved in image, pair-output and boundary terms. Observation consistency increased slightly on that subset, so real-image behavior must still be measured rather than inferred from the aggregate generated score.

## Interpretation

The training objective was achieved: the matched-geometry and mean-PSF policy improved the targeted circle geometry and did not trade away the unchanged generated scenes. The later frozen real protocol is complete and shows a short-step/de-sized-shape gain but a diameter, contour and SEM-size trade-off. See [R150 complete real validation](R150_REAL_VALIDATION_RESULTS.md).
