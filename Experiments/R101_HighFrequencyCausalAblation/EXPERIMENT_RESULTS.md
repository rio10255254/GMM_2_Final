# R101 high-frequency causal experiment results

## Status

- A/B/C and D/E/F/G were trained from scratch for 400 steps on the same continuous synthetic dataset and batch schedule.
- No checkpoint, teacher, real SEM pixel, or HS100MG structure was used for training.
- All runs completed with finite values. Full R101 training was deliberately not started.

## Main finding

The failure is not caused by insufficient epochs. The current operator-constrained family learns an easy global denoising strategy before it learns stable microscopic texture.

Arm A stayed close to identity and removed only 0.35% of held-out residual error. Its edge path received roughly 70 to 160 times less raw gradient than the radiometry path. Arm B over-expanded edge support into material regions. Arm C had a non-identity renderer whose interpolation path introduced smoothing even before learning.

Activating the dormant paths in D/E improved synthetic boundary metrics, but the serial design first removed high frequency and then attempted to reconstruct texture from the already-smoothed image. F replaced that serial conflict with parallel band synthesis. It still learned an almost global finest-band suppression: its mean finest-band gain stayed between about 0.14 and 0.16 across all PSF levels. G added a learned zero-mean high-frequency innovation path, but the training signal still rewarded broad fine-band removal.

## Comparable final metrics

| Arm | Synthetic contour distance px | Synthetic center error px | Synthetic HF error | Known motion error px | Real non-edge HF / Raw | Real strong-edge HF / Raw | Paired motion change from Raw px |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 0.1475 | 0.8185 | 1.1025 | 0.2107 | 1.0267 | 1.0422 | 0.0011 |
| D | 0.1238 | 0.7271 | 0.9579 | 0.1811 | 0.9777 | 1.3212 | 0.0077 |
| E | 0.1164 | 0.7054 | 0.9373 | 0.1943 | 0.9360 | 1.2192 | 0.0084 |
| F | 0.1153 | 0.6788 | 0.8117 | 0.1991 | 0.7809 | 1.1423 | 0.0113 |
| G | 0.1089 | 0.6997 | 0.8057 | 0.1784 | 0.7652 | 1.1303 | 0.0237 |

G has the best synthetic contour result and improves known-motion recovery, but it removes about 23.5% of real non-edge high frequency. It is therefore a useful mechanism probe, not a promotable model.

G checkpoint history also rules out “train longer” as the repair. At step 100, real non-edge high frequency had already fallen to 0.8365 of Raw. It remained near 0.77 to 0.76 from steps 200 to 400. The suppression begins early and is a learned strategy.

Tiling remains numerically close: G's mean full-versus-tiled difference is 0.00434 gray levels and its maximum is 0.0645 gray levels. Its displacement sequence remains stable in spread, but the paired vectors move farther from Raw than A, so it does not yet preserve the preferred measurement behavior.

## Root cause

1. Clean targets make deleting random sensor noise an immediately profitable action, while reconstructing correct fine texture is harder.
2. Existing losses reward lower aggregate spectral error even when structurally meaningful real texture is suppressed.
3. The original operator family can mostly reweight frequencies already present in the source. It cannot reliably synthesize content removed by the PSF.
4. Clear/identity examples are too weak to stop the global finest-band suppression.
5. The model does not learn a meaningful degradation-dependent decision; F applies almost the same finest-band reduction at every PSF level.

## R101 direction selected by this experiment

Do not extend A through G into a full run. Build R101 around a learned residual MOSR backbone with explicit low-frequency correction and a zero-mean high-frequency innovation output. The innovation path must be allowed to create missing frequency content, but it must remain translation-equivariant and be checked by subpixel-shift and overlapping-tile consistency.

The 5,000-scale training set should remain purely synthetic and continuous, but its sampling must be changed dynamically around four roles:

- clear fine-texture identity cases that must remain unchanged;
- paired independent observations of the same latent texture, so stable texture is separated from random noise;
- diverse blurred boundaries with exact continuous geometry and supersampled labels;
- flat/noise-only negatives that teach removal without teaching that every finest-band signal is noise.

Training should use target-supported multi-band phase and energy, paired-observation agreement, exact identity preservation, subpixel translation equivariance, and overlapping-context consistency. The objectives should have dynamically balanced gradient strength, and conflicting updates should be projected instead of allowing the easiest radiometry or denoising objective to dominate.

Real microscopy remains evaluation-only. Promotion must require visual comparison plus synthetic boundary, ACM/contour, x_1um displacement, and tiled-full parity evidence. No single score should act as a hard gate.
