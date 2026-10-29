# JunHua 1 um Y Reconstruction Validation

## Status

- Reconstruction: complete, 202 of 202 frames.
- Sequence interpretation: 101 physical positions, two shots per position, 100 commanded 1 um Y steps.
- Calibration: 0.125 um/px, so each 1 um step is expected to be -8 px in Y.
- External GMF for Raw and R61: historical scores are present and re-parsed.
- External GMF for the ONNX delivery model: pending because the tool currently has no license key.
- Local phase-correlation results below are supplementary and must not be called external GMF.

## Reconstruction integrity

- Source and old Raw package byte-for-byte match: True.
- MOSR output filenames exactly match source: True.
- Output dimensions and type: [[2180, 1520]], ['uint8'].
- The package default 1024-pixel tiling produced visible seams on this image size. The complete test therefore used full-frame mode (`tile-size 2200`) with the same model and optical settings.

## Local image-only displacement check

| case | mean Y step (px) | Y-step std (px) | mean abs error vs -8 (px) | mean repeat distance (px) |
|---|---:|---:|---:|---:|
| raw | -7.8911 | 0.8405 | 0.5750 | 0.0509 |
| r61 | -7.8890 | 0.6321 | 0.4433 | 0.1259 |
| mosr | -7.8831 | 0.7218 | 0.4943 | 0.0618 |

These values use every locked physical step and every same-position pair; no rows were selected or removed.

### Preliminary interpretation

- MOSR reduced the local Y-step standard deviation by 14.1% versus Raw.
- MOSR reduced the local mean absolute Y-step error by 14.0% versus Raw.
- R61 remained better in this local check: MOSR's Y-step standard deviation was 14.2% higher, and its mean absolute error was 11.5% higher.
- This supports a positive direction versus Raw, but it is not enough to claim the delivery model matches or beats R61 without its own external GMF score.
- Visually, MOSR is a mild reconstruction close to Raw, while R61 produces a much harder ring boundary.
- The default tiling seam is a delivery-package blocker and should be fixed before enterprise handoff.

## External GMF

| case | mean Y step (px) | Y-step std (px) | mean abs error vs -8 (px) | line residual RMS (px) | status |
|---|---:|---:|---:|---:|---|
| raw | -7.9552 | 4.3351 | 3.3188 | 4.7516 | complete |
| r61 | -8.0230 | 0.3420 | 0.2783 | 0.3467 | complete |
| mosr | pending | pending | pending | pending | waiting for license key |

## Files to inspect

- `results/reconstruction_comparison.png`: fixed Raw/R61/MOSR crops at positions 0, 50 and 100.
- `results/local_displacement_comparison.png`: all 100 local Y-step measurements.
- `results/default_tiling_issue.png`: evidence of the current delivery runner's default tiling seam.
- `external_gmf/paths_for_gmf_tool.tsv`: the exact three-case table for the external GMF tool.
- `external_gmf/scores/mosr/`: the folder where the new GMF_score.txt should be placed.
