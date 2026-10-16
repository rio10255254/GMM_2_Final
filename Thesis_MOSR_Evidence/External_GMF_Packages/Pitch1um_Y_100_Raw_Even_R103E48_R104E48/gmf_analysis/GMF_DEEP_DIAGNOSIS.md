# Pitch1um GMF deep diagnosis

## Main finding

R104 is pixel-identical to Raw in all 101 images. Therefore Raw-vs-R104 coordinate differences measure GMF rerun/template variability, not model behavior. R103-vs-Raw step-vector differences are of similar size to that negative-control floor.

## Negative-control floor

- Pixel-identical Raw vs R104 median step-vector difference: 10.335 px
- Pixel-identical Raw vs R104 p95 step-vector difference: 28.113 px
- R103 vs Raw median step-vector difference: 10.917 px
- R103 vs Raw p95 step-vector difference: 23.619 px

## Protocol comparison

- Current Raw full-frame, single-capture Y-step SD: 6.699 px
- Historical Raw cropped, paired-position Y-step SD: 4.335 px
- Historical R61 cropped, paired-position Y-step SD: 0.342 px
- Current/historical Raw step-SD ratio: 1.545
- Current/historical Raw line-residual ratio: 0.994

## R103 image and seam check

- Median sampled-frame mean absolute change: 0.728 gray
- Median seam/interior change ratio: 1.004
- Maximum seam/interior change ratio: 1.009
- Lowest-score 10 local change median: 0.752 gray
- Highest-score 10 local change median: 0.755 gray
- Lowest-score 10 local edge gain median: 0.710
- Highest-score 10 local edge gain median: 0.710

## Decision

The current run does not support a claim that R103 improves external-GMF stability. R104 did not alter the 8-bit images, so its apparent GMF regression is invalid as model evidence. The next controlled test should preserve both captures per position, group them to position means, and rerun Raw twice with the same locked GMF template/ROI before comparing model outputs.
