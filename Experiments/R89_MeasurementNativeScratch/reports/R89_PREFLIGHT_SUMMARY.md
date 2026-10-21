# R89 Preflight Summary

Date: 2026-08-11

## Why R88 was stopped

The previous run could satisfy stability by staying too close to Raw. Its data
sampling also did not guarantee useful structure in every motion crop, while a
confidence-controlled output could suppress learned reconstruction. R88 was
stopped at completed epoch 87 and preserved as failure evidence; none of its
weights are used here.

## R89 correction

R89 preserves the local optical bank, encoder-decoder depth, anti-aliased
sampling, no-normalization rule, and tiled-inference contract. The limited
architecture change is a direct bounded output with separate low-frequency,
detail, and edge corrections plus an auxiliary geometry head. Training pairs
now guarantee structure for motion supervision and keep Raw safety only where
the input is already clear.

An exact module comparison found all 86 shared backbone tensors have identical
names, shapes, and same-seed initial values. R89 adds 9,037 parameters, only
0.383% above R88, entirely in the revised output and auxiliary geometry heads.

## Verified before formal data

- Dataset design: 1,280 independent scenes and 5,120 observations; exact role,
  split, and corruption totals.
- Source isolation: no real pixels or real sample structure; only anonymous
  aggregate optical statistics from 300 images.
- Labels: 8x supersampled drawing followed by antialiased reduction.
- Automated checks: 17 passed, including simulated Windows reader-lock retries
  for both data generation and training progress records.
- GPU checks: all three stages completed with finite gradients. Peak allocation
  was 24.44, 27.49, and 36.64 GiB on the RTX A6000.
- Tile parity: mean 0.00014 gray, p99 0.00389 gray, maximum 0.01556 gray.
- Formal checkpoint selection uses the same 192-pixel surrounding context as
  deployment; the smaller smoke test remains an intentionally stricter bug
  detector and cannot select the formal checkpoint.
- End-to-end smoke run: completed from random initialization and produced all
  synthetic and real before/after previews.

## Imbalance found and corrected

The first learnability probe showed that the soft topology objective dominated
the image reconstruction objective. The objective decreased, but actual image
error increased. Its scale was normalized without changing the architecture.
The final 80-step probe reduced mean reconstruction error from 0.06112 to
0.05998, beating the Raw error of 0.06111, while making a measurable average
change of 1.27 gray and a maximum change of 12.08 gray.

Formal training is allowed only from the re-tested and re-frozen implementation.

## Progress-record lock incident

The first formal-data attempt stopped after 100 scenes because a live progress
read briefly locked the Windows JSON file during atomic replacement. The
incomplete formal package and the concurrently started holdout package were
moved intact under `runs/failed_data_generation` and are not reused. Both data
generation and training now retry transient reader locks; the retry behavior is
covered by automated tests before the clean regeneration.

The clean generators were then stress-tested with 34,912 live progress reads
in 12 seconds. Both processes remained active and both error logs stayed empty.

## Target-shaped clipping leakage found and removed

An audit of the first formal package found that 7.18% of observations had more
than 5% of their pixels individually clipped against the target, and the worst
observation clipped 90.86%. That can leave an artificial target-shaped trace in
the input and inflate synthetic performance. The package and its holdout were
rejected and archived before training.

The final generator applies one image-wide degradation scale based on the
99.99th percentile gap, followed only by a final outlier clip. In the new smoke
package, the maximum final clipped fraction is 0.0103% and the smallest global
scale is 0.502. The audit now hard-fails above 0.0200% clipping or below 0.30
global scale.

## Windows Unicode-path inference

The deployment reader initially failed on the real folder whose name contains
Chinese characters. Image input/output was changed to a Unicode-safe path, then
tested with both 8-bit BMP and 16-bit TIFF files and with a real 1536x2048 image
from the Chinese-named displacement folder. The actual reconstruction output
was written successfully. The model, trainer, data generator, and data content
were unchanged; GPU and tiled-parity checks were rerun before the final lock.
