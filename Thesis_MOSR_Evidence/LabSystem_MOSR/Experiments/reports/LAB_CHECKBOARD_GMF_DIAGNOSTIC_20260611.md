# Lab Checkboard GMF Diagnostic - 2026-06-11

## Question

Why did the main project show clear external GMF gains, while the current
LabSystem checkboard run shows only a very small improvement?

## Short Answer

The current result is not evidence that the whole method stopped working.
It is mainly a different comparison.

The main project's large gains were measured on the formal three-scale ring
benchmark, where new candidates were compared against the older R30 baseline.
The current LabSystem readout compares raw laboratory checkboard frames against
the first Lab R39/R40 reconstructions on one real continuous-displacement
sequence.

On this Lab sequence, the raw measurement is already strong after the shared
abnormal interval is set aside diagnostically. The latest checkpoints mostly
shift the absolute GMF position by a nearly constant offset, which does not
reduce the step-to-step variation much. The newly scored tradeoff checkpoints
do help slightly more, but the gain is still small.

A follow-up corner-geometry validation changes the root-cause emphasis. Across
51 frames and 358 raw checkboard corners, the reconstructed images frequently
move the strongest local corner response away from the raw corner location. This
supports the visual observation that hard right-angle corners are being
reshaped. The acquisition sequence still affects the GMF score, but the model
also has a real target-domain problem on checkboard corners.

## Main Project Reference

The formal main-project improvement is large because it is a model-to-model
comparison on the standard ring sequence:

| Case | 0.8px step_std | 0.08px step_std | 8px step_std |
|---|---:|---:|---:|
| R30 former baseline | 0.167862 | 0.157720 | 0.205193 |
| COMBO formal baseline | 0.131560 | 0.099891 | 0.154515 |
| COMBO change vs R30 | -21.6% | -36.7% | -24.7% |

That result is the formal baseline evidence for the project. It should not be
mixed directly with a one-sequence Lab checkboard raw-vs-reconstruction readout.

## Current Lab Checkboard Readout

The current external GMF package has five cases:

| Case | step_std full series | Change vs raw |
|---|---:|---:|
| Raw input | 0.260669 px | baseline |
| Lab R39 latest | 0.257648 px | -1.16% |
| Lab R40 latest | 0.255399 px | -2.02% |
| Lab R39 tradeoff | 0.254427 px | -2.39% |
| Lab R40 tradeoff | 0.255418 px | -2.01% |

One interval is abnormal in all five cases:

| Case | Interval | Step |
|---|---|---:|
| Raw input | 16-07-42 to 16-08-18 | 7.474 px |
| Lab R39 latest | 16-07-42 to 16-08-18 | 7.437 px |
| Lab R40 latest | 16-07-42 to 16-08-18 | 7.431 px |
| Lab R39 tradeoff | 16-07-42 to 16-08-18 | 7.396 px |
| Lab R40 tradeoff | 16-07-42 to 16-08-18 | 7.417 px |

If that shared interval is removed only as a diagnostic check:

| Case | step_std after removing shared abnormal interval |
|---|---:|
| Raw input | 0.109431 px |
| Lab R39 latest | 0.113533 px |
| Lab R40 latest | 0.109906 px |
| Lab R39 tradeoff | 0.107612 px |
| Lab R40 tradeoff | 0.108066 px |

This means the headline full-series improvement is still strongly affected by
one shared sequence irregularity. Without that interval, the tradeoff
checkpoints now beat raw slightly, while the latest checkpoints remain tied or
worse.

## What The Reconstructions Actually Changed

Compared with raw input, the GMF positions moved mostly by a stable offset:

| Case | Mean PosY shift vs raw | PosY shift std | Step-change std vs raw |
|---|---:|---:|---:|
| Lab R39 latest | +0.451 px | 0.026 px | 0.029 px |
| Lab R40 latest | +1.471 px | 0.030 px | 0.024 px |

This is important because external GMF step_std is based on frame-to-frame
movement. A nearly constant position shift cancels out when computing steps.
So the model can visibly change the reconstruction and still barely change the
step stability score.

The pixel-level reconstruction changes are also modest:

| Case | Mean absolute image change vs raw | Approx. share of raw image std |
|---|---:|---:|
| Lab R39 latest | 1.80 gray levels | 9.29% |
| Lab R40 latest | 2.02 gray levels | 10.46% |

This is consistent with small GMF movement changes.

## Sequence Quality Findings

The first captured image is missing from all three returned GMF score files.
Each case therefore has 50 GMF rows and 49 measured step intervals.

The raw sequence also shows timing irregularity:

| Quantity | Value |
|---|---:|
| Capture gap min | 7 s |
| Capture gap median | 8 s |
| Capture gap max | 77 s |
| Correlation between capture gap and step size | 0.494 |

The largest step error is the same shared abnormal interval:

| Interval | Gap | Step | Deviation from expected 1 um step |
|---|---:|---:|---:|
| 16-07-42 to 16-08-18 | 36 s | 7.474 px | +1.677 px |

This points to a shared capture, stage, or sequence issue. Reconstruction cannot
reliably fix a real displacement irregularity that appears in every case.

## Why The Improvement Is Small

Ranked causes:

1. The Lab training and validation data do not directly cover the real
   checkboard-corner target. A dedicated corner-geometry validation found that
   reconstructed corners are often shifted or reshaped relative to raw:
   - raw median corner-response shift: 1.414 px,
   - Lab R39 latest: 3.606 px,
   - Lab R40 latest: 3.606 px,
   - Lab R39 tradeoff: 9.220 px,
   - Lab R40 tradeoff: 4.243 px.
   The current Lab packages also have 0 checker/checkboard/chessboard-specific
   training paths.
2. The comparison changed. The main project compared stronger candidates against
   an older R30 baseline on a formal ring benchmark. The Lab readout compares
   raw checkboard frames against first-pass Lab reconstructions on one real
   sequence.
3. The raw Lab checkboard sequence is already very steady once the shared
   abnormal interval is separated diagnostically. There is little remaining
   step variation for the model to reduce.
4. The dominant full-series variation is shared across raw, R39, and R40. This
   makes it look like the models barely help, because the main disturbance is
   not reconstruction-specific.
5. The Lab latest checkpoints were chosen for validation reconstruction quality,
   not external GMF stability. After external scoring, the tradeoff checkpoints
   are slightly better for this GMF sequence, especially R39 tradeoff.
6. The image family changed. The main formal benchmark is ring based, while the
   current validation target is a laboratory checkboard sequence.

## Practical Verdict

The current best Lab checkboard result is R39 tradeoff, but it is not yet a
strong measurement-improvement result.

The evidence says:

- full-series Lab R39 tradeoff is only 2.39% better than raw,
- after removing the shared abnormal interval diagnostically, Lab R39 tradeoff
  is 1.66% better than raw,
- the current limiting factor is not only acquisition. The stronger visual
  failure is that the model does not preserve real checkboard corner geometry.

## Recommended Next Actions

1. Add a Lab checkboard/corner validation family before more full training or
   model averaging.
2. Add checkboard-like right-angle samples to the Lab data generator and score
   corner-response shift before external GMF.
3. Build a Lab R39/R40 weight-average candidate only after the corner check is
   available, because averaging can hide but not necessarily fix corner
   reshaping.
4. Prepare a cleaner repeat acquisition with no missing first frame and a more
   stable capture cadence.
5. Keep raw input as an explicit baseline in every Lab GMF report.
6. Do not promote or reject the Lab model from this one checkboard readout.
   Treat it as first evidence that the Lab pipeline runs, not as final proof of
   measurement improvement.
