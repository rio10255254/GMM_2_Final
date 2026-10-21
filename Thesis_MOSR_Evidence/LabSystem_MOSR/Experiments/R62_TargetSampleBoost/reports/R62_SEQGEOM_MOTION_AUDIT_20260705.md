# R62 sequence/motion training audit, 2026-07-05

## What was checked

This audit checked whether the current model already had displacement-oriented training, and whether that training actually affected the weights used for reconstruction.

## Main finding

The displacement training path existed, but the latest target-sample run was not using it effectively.

Three separate issues were found:

1. The sequence-geometry loss existed, but the R62 target candidates were still mostly using the older generated sequence source. The self-shift target-sample data was not routed into the strongest center/step geometry loss path.
2. The self-shift filenames used `seq00060_p000_f001`, but the motion-pair loader only recognized the older `seq00060_f001` style. This meant the new exact-motion pairs could be missed by the motion loader.
3. With AMP enabled, formal training could report normal losses but leave the actual model weights almost unchanged. A no-AMP probe and no-AMP short run confirmed that the same candidate can update p1, p2, output, and boundary-adapter weights when AMP is off.

## Changes made

1. Added support for candidate-level sequence routing in the R61/R62 launcher.
2. Added a V6 candidate that routes the existing sequence-geometry loss to the self-shift target-sample data.
3. Added a V7 candidate that keeps the V6 route but increases practical update mobility.
4. Fixed sequence/motion filename parsing so files like `seq00060_p000_f001` are recognized.
5. Set V7 to run with AMP off by default.

## Verification

All R62 target-boost tests passed:

- 8 passed.

Dry-run confirmed V7 uses:

- self-shift target-sample sequence data
- self-shift target-sample motion pairs
- no real-motion ROI pairs for motion loss
- AMP off
- trainable boundary_adapter, p1, p2, and out layers

## Short-run results

### V7 no-AMP, lr 1.2e-6, 2 epochs x 80 batches

This proved the model can now really update, but it was too aggressive.

- Sequence score improved: 0.7552 -> 0.7710.
- Validation reconstruction improved: 0.013924 -> 0.012477.
- SSIM improved: 0.8626 -> 0.8773.
- Edge width shrank too much: about 6.94 -> 6.08.

Decision: do not use this learning rate as the default.

### V7 no-AMP, lr 3.0e-7, 2 epochs x 80 batches

This was more balanced.

- Sequence score improved: 0.7552 -> 0.7615.
- Sequence delta error improved: 0.5988 -> 0.5830.
- Sequence gradient error improved: 0.7807 -> 0.7665.
- Validation reconstruction improved: 0.013924 -> 0.013313.
- SSIM improved: 0.8626 -> 0.8688.
- Edge width shrank: 6.9428 -> 6.5413.
- p1, p2, output, and boundary-adapter weights all changed.

Decision: use lr 3.0e-7 as the current safer default for V7.

## Current recommendation

The next long run should use:

- candidate: `r62_target_selfshift_seqgeom_mobility_v7`
- AMP off by default
- learning rate: 3.0e-7
- monitor edge width closely

The run is now genuinely updating the model, but it still tends to sharpen boundaries. That may help displacement and edge localization, but it must be checked against CD/shape preservation before calling it the final thesis model.
