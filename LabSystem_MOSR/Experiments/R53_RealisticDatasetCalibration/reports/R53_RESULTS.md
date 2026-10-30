# R53_RESULTS

## Current Status

R53 completed the Lab-system realistic dataset calibration round. It is not
promoted. The formal 100-epoch run completed, but the real Lab checkboard
corner gate failed.

## Why This Round Exists

R52 improved the median real-corner shift but still worsened the large-shift
corner rate. The visual audit also showed that recent Lab packages were too
checkboard/corner-heavy and not close enough to the main-project mixture of
gray textures, microscopy detail, and varied geometry. R53 rebuilds the data
package before judging the model again.

## Data Package

The train package has 6000 pairs:

| Role | Count |
|---|---:|
| ring | 700 |
| shape | 700 |
| micro/detail | 900 |
| mixed-PSF corner | 300 |
| realistic boundary | 2050 |
| real background / real texture | 950 |
| masked CAD anchor | 400 |

The validation package has 1740 held-out pairs. The train/validation split was
checked for source-path overlap.

## CAD Anchor Policy

The CAD-derived real checkboard samples use the reliable-mask policy inherited
from R49: inside the mask the label uses CAD GT; outside the mask the label is
kept equal to the source image. The R53 package also copies each CAD mask into
the materialized package so later masked-loss work can reuse it.

## PSF Policy

The explicit checkboard-corner subset uses three blur sources evenly:

- formal BADS: 100 train, 40 val
- Gaussian control: 100 train, 40 val
- weak-BADS alpha 0.50: 100 train, 40 val

The launcher uses the Lab PSF file:
`LabSystem_MOSR/psf_calibration/results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat`

## Verification Completed

- R53 tests passed: 7 tests
- Real package plan and split validation passed
- Train and validation packages were materialized
- Dataset contact sheet was inspected
- Smoke training passed at batch 16
- Batch 32 probe passed
- Batch 48 probe failed with CUDA out of memory
- Worker-8 formal attempt reached epoch 2 but failed at validation worker startup with a Windows-side `MemoryError`
- Worker-4 stability run passed epoch 2 validation
- Worker-4 formal attempt with PSF-forward loss active reached epoch 11, then became unacceptably slow when `w_phys` first activated
- Worker-4 no-PSF-forward stability run passed epoch 12
- Worker-4 batch-32 no-PSF-forward formal attempt reached epoch 11, then failed with CUDA out of memory when shift equivariance activated
- Formal 100-epoch scratch training completed at batch 16 / workers 4 with PSF-forward loss disabled
- Real Lab checkboard reconstruction completed for both `best_tradeoff` and `latest`
- Real-corner gate failed for both R53 checkpoints

## Formal Training

- Model name: `LAB_GESR_v1_v5_ST0p8_SWP_r53_realistic_calibrated_scratch_formal_b016_w04_nophys_e100`
- Progress directory: `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r53_realistic_calibrated_scratch_formal_b016_w04_nophys_e100_20260616_154939`
- Log pointer: `LabSystem_MOSR/Experiments/R53_RealisticDatasetCalibration/results/formal_training_logs/latest_formal_training_log.txt`
- Start setting: scratch training, 100 epochs, batch 16, validation batch 4, 4 workers, Lab PSF path configured, PSF-forward loss disabled
- Completed epochs: 100
- Internal validation improved through the end: epoch 100 validation total `0.045247`, PSNR `26.39`, SSIM `0.9353`
- The training script's `best_tradeoff` stayed at epoch 15 because the later best-update window closed at epoch 60; therefore both `best_tradeoff` and `latest` were reconstructed.

## Real Checkboard Gate

The real Lab `20250605_checkboard` sequence was reconstructed and checked on
51 frames / 358 accepted raw checker corners.

| Case | Median corner shift (px) | P75 shift (px) | Corners > 5 px shift |
|---|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% |
| Lab R40 tradeoff | 4.243 | 5.000 | 24.581% |
| Lab R51 mixed-PSF best | 2.828 | 9.220 | 36.872% |
| Lab R52 stability latest | 3.606 | 8.485 | 30.447% |
| Lab R53 realistic best | 3.606 | 9.899 | 40.782% |
| Lab R53 realistic latest | 9.220 | 9.899 | 58.939% |

Gate verdict:

- `lab_r53_realistic_best_tradeoff`: failed. It improves median versus Lab R40 but worsens the large-shift rate and tail.
- `lab_r53_realistic_latest`: failed. It worsens median, large-shift rate, and tail versus Lab R40.

The key lesson is that the R53 realistic data mix made the internal validation
look better, but that improvement did not transfer to real Lab checker corners.
The final `latest` checkpoint is especially unsafe for the real checkboard
case despite having the best internal validation score.

## Artifacts

- Checkboard validation report: `reports/R53_CHECKBOARD_VALIDATION.md`
- Best checkpoint gate JSON: `results/r53_best_tradeoff_corner_gate.json`
- Latest checkpoint gate JSON: `results/r53_latest_corner_gate.json`
- R53 reconstruction output root: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/r53_reconstruction_outputs`
- R53 GMF-ready case folders: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r53_realistic_best_tradeoff` and `...\lab_r53_realistic_latest`

## Next Direction

Do not use R53 as a Lab baseline. The next useful step is not simply more
epochs on the same data mix; the real-corner failure shows that the objective
can still prefer visually stronger or internally better reconstructions while
misplacing real checker corners.
