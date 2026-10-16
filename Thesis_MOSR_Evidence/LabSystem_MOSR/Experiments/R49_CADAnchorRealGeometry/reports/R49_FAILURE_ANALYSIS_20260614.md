# R49 Failure Analysis - 2026-06-14

## Short Verdict

R49 failed for a real reason, not because training crashed.

The CAD-anchor data made the model better at the internal patch task, but that
task did not enforce the real checkboard corner position. As training continued,
the model could improve PSNR/SSIM while still moving or weakening the true
corner response.

## Evidence

| Item | Result |
|---|---:|
| Real frames checked | 51 |
| Raw corners checked | 358 |
| Lab R40 median corner shift | 4.243 px |
| Best R48 median corner shift | 6.708 px |
| R49 best_tradeoff median corner shift | 14.213 px |
| R49 best_detail_guarded median corner shift | 14.213 px |
| R49 latest median corner shift | 9.000 px |
| R49 latest corners > 5 px shift | 85.475% |

`best_tradeoff` and `best_detail_guarded` have different checkpoint hashes, but
they produced identical real checkboard output for the inspected frame and
identical aggregate corner metrics. In practical terms, R49 only produced two
real behaviors: the conservative E50 output and the final E100 output.

## What The Two R49 Behaviors Mean

### E50 / best_tradeoff

This version barely changes the full image, but it weakens the local corner
response. Its median local change versus raw is only `0.036`, yet the median
corner shift is `14.213 px` and the median edge strength is below raw. This is
not useful deblurring; it is a conservative, low-response corner result.

### E100 / latest

This version changes the image more and is somewhat stronger locally, but it
creates widespread wrong corner responses. The median shift improves to `9.000
px`, but `85.475%` of corners move more than 5 px. The visual sheet also shows
edge artifacts and black-white halo behavior.

## Root Cause Assessment

### 1. The training validation target was not the real target

The internal validation kept improving through epoch 100:

| Epoch | Validation PSNR | Validation SSIM |
|---:|---:|---:|
| 2 | 24.25 | 0.904 |
| 50 | 27.17 | 0.931 |
| 100 | 27.74 | 0.944 |

But the real checkboard corner metric got worse. This means the held-out
CAD-anchor patch task is not enough to represent the real target: preserving
the exact corner-response position on the real sequence.

### 2. CAD-anchor labels were too strong relative to the real source

Inside the trusted CAD mask, the average source-to-label difference is about
`0.21` to `0.22` in normalized grayscale. That is a large correction. It asks
the model to push real captured edges toward a hard CAD black/white target, not
just repair small blur.

That can create two bad outcomes:

- The model resists the correction and produces a blurred, low-response corner.
- The model follows the correction too hard and creates halo/artifact behavior.

R49 produced both patterns.

### 3. Real CAD data was real, but not automatically aligned with the final task

The CAD anchors came from the high-quality `20260613` real checkboard/CAD
reference set. The final check was the separate `20250605_checkboard` sequence.
Both are Lab-system data, but they are not the same validation target.

R49 assumed that real CAD anchors would transfer directly. The result shows that
this assumption is false unless the target metric is explicitly included.

### 4. The old synthetic mix diluted the new signal

The final training mix was 400 CAD-anchor pairs out of 4000 total pairs. This
small slice was enough to disturb the model, but not enough to teach stable
real-corner geometry. The remaining data still rewarded older synthetic edge
behavior and did not directly punish real corner movement.

### 5. Checkpoint selection did not use the real corner metric

The formal best checkpoint was selected by the existing training score. That
score picked epoch 50. The final epoch had better PSNR/SSIM. Neither choice was
good on the real corner table.

The lesson is direct: future Lab training cannot choose checkpoints without a
real checkboard corner validation loop.

## What I Should Have Done Differently

1. I should have made the real-corner metric a first-class validation gate
   before running a full 100 epochs.
2. I should have tested whether the CAD target and the real corner metric agree
   on corner position before trusting the CAD-anchor training target.
3. I should not have assumed that "more real data" automatically means better
   transfer.
4. I should have treated the large source-to-CAD label difference as a risk,
   not just as stronger supervision.
5. I should have run an early 10-20 epoch real checkboard reconstruction before
   committing to the full run.

## Next Design Direction

Do not continue R49 by simply increasing epochs, CAD-anchor ratio, or edge loss.

The next design should add a direct real-corner constraint:

1. Use real checkboard frames as an always-on validation gate.
2. Compare reconstructed corners against CAD GT where CAD GT exists.
3. Also require that corner response does not drift badly on real frames without
   CAD GT.
4. Use softer CAD targets or optical-profile targets instead of hard binary CAD
   masks.
5. Select checkpoints by real corner behavior first, then use image quality as a
   secondary filter.

The current evidence says the problem is not lack of epochs. It is a mismatch
between the training objective and the real corner geometry we need.
