# R62 V8 GMF / Pairwise Displacement Progress - 2026-07-06

## Completion Standard

This round is not considered complete merely because a new model trained. The target is:

- thesis displacement images are reconstructed with the candidate checkpoint,
- displacement is measured by an open in-house method,
- stability is better than Raw on the thesis-critical cases,
- the result is not caused by a tracking artifact,
- and the model does not create obvious failures on the other magnifications.

## What Was Added

1. The fixed GMF-like gate can now compare extra candidate reconstructions without editing hard-coded case names.
   - Tool: `run_thesis_gmf_gate.py`
   - New option: `--extra-case case=relative_template`

2. The R62 reconstruction launcher can now reconstruct the thesis displacement datasets with any selected checkpoint.
   - Tool: `run_r62_reconstruction_for_new_displacement_sets.py`
   - New options: `--weights`, `--case-prefix`, `--role`, `--dry-run`

3. The GMF-like displacement tool now has a `pairwise` mode.
   - Old `multi` mode tracks features forward from the first frame.
   - New `pairwise` mode redetects features in every adjacent image pair before fitting the common displacement.
   - This prevents the feature set from shrinking across a long sequence and causing late-frame mismatches.

## Verification

Related automated checks passed:

```text
17 passed in 0.18s
14 passed in 0.22s
12 passed in 0.22s
```

These cover:

- V8 launcher configuration,
- configurable reconstruction commands,
- fixed GMF gate case extension,
- GMF-like Gaussian fitting,
- and the new pairwise GMF mode.

## V8 Training Probe

A short V8 training probe was completed:

- Candidate: `r62_target_selfshift_gmfgate_v8`
- Run: `v8_gmfgate_probe_e1_mtb120_b8_20260706`
- Training amount: 1 epoch, capped at 120 batches
- Base checkpoint: R61 v16
- Output checkpoint: `best_tradeoff.pth.tar`

Internal sequence validation changed only slightly:

- before training: sequence score about `0.7552`
- after 120 batches: sequence score about `0.7593`

This means the 120-batch V8 probe is a valid trained checkpoint, but it is not yet strong evidence of a major model improvement.

## Reconstruction Completed

The following thesis displacement groups were reconstructed with the V8 120-batch checkpoint:

- `20260702_100MG`, `x_1um`
- `20260702_100MG`, `x_0p5um`
- `20260704_20x_5x`, `20x_1um`
- `20260704_20x_5x`, `20x_0p5um`
- `20260704_20x_5x`, `5x_1um`
- `20260704_20x_5x`, `5x_0p5um`

All six groups produced the expected image counts.

## Why The First GMF Result Looked Bad

The first fixed GMF-like gate used the old `multi` tracking mode.

On `20260702_100MG x_1um`, Raw stayed stable, but reconstructed images failed near the end of the sequence because the tracked feature count dropped from about 60 to only a few features. The last steps then jumped to impossible values such as about `+20 px`, which inflated the standard deviation.

This was not a clean proof that the model destroyed displacement information. It was a tracking failure triggered more easily by reconstructed images.

## Pairwise GMF Results

The new pairwise GMF mode gives the more reliable readout.

| Dataset | Group | Best case | Raw std um | R61 std um | V7 std um | V8 probe std um | V8 probe vs Raw |
|---|---:|---|---:|---:|---:|---:|---:|
| 20260702_100MG | x_1um | V7 | 0.009536 | 0.009402 | 0.009362 | 0.009396 | +1.47% |
| 20260702_100MG | x_0p5um | V8 probe | 0.052563 | 0.052388 | 0.052373 | 0.052366 | +0.38% |
| 20260704_20x_5x | 20x_1um | Raw | 0.025065 | 0.025353 | 0.025344 | 0.025439 | -1.49% |
| 20260704_20x_5x | 20x_0p5um | Raw | 0.076356 | 0.077545 | 0.077201 | 0.077277 | -1.21% |
| 20260704_20x_5x | 5x_1um | V8 smoke | 0.160710 | 0.157254 | 0.158132 | 0.172859 | -7.56% |
| 20260704_20x_5x | 5x_0p5um | Raw | 0.012163 | 0.026884 | 0.025546 | 0.024762 | -103.59% |

Positive means the V8 probe is more stable than Raw. Negative means it is worse than Raw.

## Current Interpretation

The pairwise GMF result is useful and much fairer than the old tracking mode.

For the thesis-critical 100MG sample:

- reconstructed images are at least comparable to Raw,
- V7 is best on the 1 um sequence,
- V8 probe is best on the 0.5 um sequence,
- and the catastrophic old GMF failure disappears.

For cross-magnification generality:

- 20x is nearly tied, with Raw still slightly ahead,
- 5x is not solved,
- and V8 120-batch training is not broadly stronger than V7/R61.

So the honest conclusion is:

> The model is defensible on the main 100MG thesis displacement sample under pairwise GMF, but V8 is not yet a universal improvement. A long training run is not justified unless the next version directly selects against the remaining 20x/5x failures.

## Next Training Direction

Do not simply run V8 for many more hours yet.

The next candidate should be V9 and should change the selection target:

1. Keep the R61/V7 boundary and CD strengths.
2. Add the pairwise GMF gate as the external validation target.
3. Penalize cases where reconstruction makes pairwise GMF worse than Raw.
4. Use 100MG as the thesis-priority target, but keep 20x and 5x as guardrails so the model does not overfit the thesis sample too aggressively.
5. Prefer checkpoints that improve 100MG while not breaking 20x/5x.

Long training becomes worthwhile only after a short V9 probe moves the pairwise GMF table in the right direction.

## Key Artifacts

- Pairwise GMF full results:
  `thesis_gmf_pairwise_gate_v8_probe_mtb120_20260706_full`
- V8 120-batch reconstruction summary:
  `r62_v8_gmfgate_probe_mtb120_psfoff_reconstruction_summary.json`
- V8 120-batch training run:
  `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_gmfgate_v8_v8_gmfgate_probe_e1_mtb120_b8_20260706_20260706_012819`
- Original fixed multi-mode GMF comparison:
  `thesis_gmf_like_fixed_gate_v8_probe_mtb120_20260706`
