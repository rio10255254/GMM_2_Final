# Lab GMF Root-Cause Deep Probe - 2026-06-11

## Question

The main project clearly improved external GMF before. Why does the LabSystem
checkboard readout show almost no improvement once the shared abnormal interval
is set aside?

## Completion Criteria

This probe is considered useful only if it separates these possibilities:

- acquisition/sequence limitation,
- training-data or target mismatch,
- PSF mismatch,
- checkpoint/model-selection mismatch,
- inference or packaging error.

## What Was Checked

### Main-Project Success Condition

The main-project improvement is real, but it was measured on the formal
three-scale ring workflow.

| Candidate | 8px | 0.8px | 0.08px |
|---|---:|---:|---:|
| R30 former baseline | 0.205193 | 0.167862 | 0.157720 |
| COMBO formal baseline | 0.154515 | 0.131560 | 0.099891 |
| COMBO change vs R30 | -24.7% | -21.6% | -36.7% |

The later R39/R40 family also worked mainly through weight averaging and
tradeoff checkpoints, not by treating raw real checkboard frames as the direct
baseline.

| Main-project candidate | 8px vs COMBO | 0.8px vs COMBO | 0.08px vs COMBO | Role |
|---|---:|---:|---:|---|
| R39 a030 | -6.94% | +6.42% | -15.97% | endpoint tradeoff |
| R40 a043 | -5.91% | -3.15% | +21.52% | endpoint tradeoff |
| R39R40 a025 | -5.18% | +1.51% | +0.51% | balanced alternate |

### Lab Training Data Scope

The Lab training-data pipeline reused the main-project structure and copied the
core scripts, but the first Lab foundation is smaller than the current full
main-project data tree.

| Data root | Base generated images | Stage folders |
|---|---:|---:|
| Main project generated data | 8668 | 48 |
| Lab first foundation | 2968 | 33 |

The Lab R39/R40 packages were materialized:

| Package | Lab count |
|---|---:|
| ring replay pairs | 1100 |
| R39 safe package | 1240 |
| R39 strong package | 1590 |
| R39 held-out validation | 210 |
| R40 microscopy train | 1300 |
| R40 held-out validation | 100 |

The Lab `Data_Simulaion.py` differs from the main copy only by small Lab-run
controls. The Lab `PSF_Convolution.py` differs mainly by Lab PSF path support,
Gaussian-control support, and stage/noise environment controls.

### Lab PSF Condition

The selected Lab BADS PSF is valid and much more centroid-stable than the first
coarser fit, but it is not clearly better than the Gaussian control on the
edge-forward metric.

| PSF check | Value |
|---|---:|
| Fine BADS median edge RMSE | 0.101789875 |
| Fine BADS gap vs Gaussian | +9.242% |
| Fine PSF centroid span | 0.038 px |

This does not invalidate the PSF, but it leaves a plausible mismatch: the
synthetic Lab blur may not be the exact limiting blur seen by the real
checkboard GMF sequence.

### Current Lab Checkboard Sequence

The returned external GMF scores now cover raw, Lab R39/R40 latest, and Lab
R39/R40 tradeoff.

| Case | External GMF step_std | Change vs raw |
|---|---:|---:|
| Raw input | 0.260669 px | baseline |
| Lab R39 latest | 0.257648 px | -1.16% |
| Lab R40 latest | 0.255399 px | -2.02% |
| Lab R39 tradeoff | 0.254427 px | -2.39% |
| Lab R40 tradeoff | 0.255418 px | -2.01% |

One interval is abnormal in all cases:

| Interval | Raw step |
|---|---:|
| 16-07-42 to 16-08-18 | 7.474 px |

If that shared interval is removed only as a diagnostic:

| Case | step_std without shared abnormal interval |
|---|---:|
| Raw input | 0.109431 px |
| Lab R39 latest | 0.113533 px |
| Lab R40 latest | 0.109906 px |
| Lab R39 tradeoff | 0.107612 px |
| Lab R40 tradeoff | 0.108066 px |

The first captured frame is also missing from all returned GMF score files.
The raw capture gaps range from 7 s to 77 s, and the gap-to-step correlation is
about 0.494. This points to acquisition/sequence behavior as a major driver of
the current readout.

### Inference And Packaging

The current Lab inference did not silently skip the sequence:

- raw, R39 latest, and R40 latest cases each contain 51 BMPs,
- filenames match across cases,
- Lab PSF was passed explicitly,
- the model physics and weak-PSF paths were active,
- inference completed all frames.

This makes a basic inference/packaging failure unlikely.

### Checkpoint Probe Added

This probe also reconstructed and externally scored the auto tradeoff
checkpoints:

| New case | Frame count | Mean absolute change vs raw | External step_std |
|---|---:|---:|---:|
| Lab R39 best_tradeoff | 51 | 1.408 gray levels | 0.254427 px |
| Lab R40 best_tradeoff | 51 | 1.389 gray levels | 0.255418 px |

These two cases are now included in the same five-case external GMF analysis.

A local phase-correlation proxy was also run. This is not a replacement for the
external GMF tool, but it confirmed that the same large-step interval remains
dominant.

### Corner Geometry Validation

The visual concern that checkboard right angles are being rounded or reshaped
was tested directly after the GMF readout.

The validation scanned all 51 checkboard frames, accepted 358 raw checkboard
corners, and compared the raw local corner patches against R39/R40 latest and
tradeoff reconstructions.

| Case | Median corner-response shift | Corners > 5 px shift | Median local change vs raw |
|---|---:|---:|---:|
| Raw input | 1.414 px | 1.676% | 0.000 |
| Lab R39 latest | 3.606 px | 47.765% | 0.058 |
| Lab R40 latest | 3.606 px | 38.268% | 0.066 |
| Lab R39 tradeoff | 9.220 px | 52.514% | 0.071 |
| Lab R40 tradeoff | 4.243 px | 24.581% | 0.068 |

This means the reconstructions often move the strongest local corner response
away from the raw corner position. The visual contact sheet also shows
hard-looking edges, shifted corner locations, and dark edge halos. This is a
separate failure mode from the shared abnormal displacement interval.

Training coverage was checked from the Lab manifests:

| Package | Total pairs | Rectangle pairs | Micro-grid pairs | Checkboard-specific pairs |
|---|---:|---:|---:|---:|
| R39 safe training | 1240 | 20 | 0 | 0 |
| R40 training | 1300 | 50 | 80 | 0 |

The Lab training tree has no checker/checkboard/chessboard-specific paths. The
current validation sets are shape or microscopy validation sets, not real
checkboard-corner validation sets.

## Root-Cause Ranking

### 1. Training-data / target mismatch on checkboard corners - high confidence

The reconstructed images frequently shift or reshape local checkboard corner
geometry. This persists across all four Lab reconstruction cases and is visible
both numerically and in the corner contact sheet.

The Lab packages contain rectangles and micro-grid samples, but no direct
checkboard-specific training or validation family. The current validation score
can therefore improve on synthetic shape/microscopy splits while the real
checkboard corner geometry is damaged.

### 2. Comparison mismatch and acquisition limitation - high confidence

The old success was a formal ring benchmark comparison against older model
baselines. The current Lab readout is raw real checkboard versus reconstruction
on one acquisition sequence.

The shared abnormal step and timing irregularity are present before and after
reconstruction, so the model cannot fully fix the dominant full-series GMF
error. However, the corner validation shows that acquisition is not the only
problem.

### 3. Checkpoint/model-selection mismatch - medium confidence

The latest checkpoints were chosen by synthetic validation quality. The
external GMF readout slightly favors R39 tradeoff, while the corner validation
shows that neither latest nor tradeoff is reliably preserving checkboard
corners.

### 4. Missing Lab mixed candidate - medium-low confidence

The old best balanced result was not a plain endpoint. It was COMBO or a
R39/R40 weight average. The Lab checkboard result now shows that R39 tradeoff is
better than the latest checkpoints, but the Lab R39/R40 mixed candidate still
has not been built or externally scored. After the corner validation, this is no
longer the first thing to do; it should wait until a checkboard-corner guard
exists.

### 5. PSF mismatch - medium confidence

The Lab BADS PSF is valid, but its forward edge score is still worse than the
Gaussian control. This may mean the first Lab synthetic blur does not perfectly
match the real checkboard capture.

### 6. Basic inference error - low confidence

The inference logs and file counts do not support a simple packaging or script
failure as the cause.

## Practical Conclusion

The strongest current explanation is:

The Lab model is running, but it does not yet preserve real checkboard corner
geometry. The weak GMF gain is therefore not just a sequence artifact. The
model is sharpening or reshaping edges in a way that can make corners look
cleaner but geometrically wrong.

This does not prove the Lab model is useless. It shows that the current Lab
training target is incomplete for this sample. A checkboard/corner validation
and data family should be added before more long training or model averaging is
treated as meaningful.

## Actions Completed In This Probe

- Compared main-project formal GMF results against the Lab checkboard result.
- Compared main and Lab data-generation scope and script differences.
- Checked Lab PSF validation status.
- Verified that latest inference processed all 51 frames with Lab PSF active.
- Reconstructed Lab R39/R40 `best_tradeoff` checkpoints.
- Added `lab_r39_best_tradeoff/` and `lab_r40_best_tradeoff/` to the external
  GMF case package.
- Parsed the returned tradeoff GMF text files and updated the five-case
  analysis.
- Updated the GMF package README and result-drop README with the new cases.
- Added a full 51-frame checkboard corner-geometry validation with 358 raw
  corners and 1790 case measurements.
- Audited the Lab R39/R40 manifests for checkboard-specific training coverage.

## Next Required Evidence

1. Add a Lab checkboard/corner validation family and use it as a guard before
   external GMF.
2. Add checkboard-like right-angle samples to the Lab generator, including
   sharp and blurred corners, varied cell widths, brightness, and off-center
   positions.
3. Re-test R39/R40 latest, tradeoff, and any mixed candidate using the new
   corner guard before treating external GMF changes as meaningful.
4. Re-acquire a clean checkboard sequence with:
   - no missing first frame,
   - fixed cadence,
   - no long pause between steps,
   - raw input retained as the baseline.
5. If the corner guard passes but clean-sequence GMF still shows only small
   gains, then revisit PSF and acquisition as the remaining limiting factors.
