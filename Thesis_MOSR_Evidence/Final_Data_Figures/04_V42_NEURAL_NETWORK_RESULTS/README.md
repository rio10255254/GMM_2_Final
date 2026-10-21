# Chapter 6.2 MOSR and Wiener result package

This folder contains the current Chapter 6 evidence for Raw images, fitted-PSF Wiener deconvolution, and MOSR reconstruction. It covers structure identity, edge sharpness, SEM-anchored CD, and displacement measurement.

## Current baseline

- The Wiener result uses the fitted PSF for each magnification and a fixed NSR of 0.05 for both 20× and 50×.
- The same PSF and NSR are used for both displacement amplitudes at a given magnification.
- Moderate ringing is intentionally retained so the traditional baseline is visibly sharp; it is not tuned using SEM CD or displacement outcomes.
- Raw, Wiener, and MOSR image examples share the same 0–255 display range. No per-image contrast stretching is used.

## Contents

- `figures/`: 29 individual English MATLAB figures.
- `tables/`: 18 source and summary tables for contrast, edge width, CD, displacement, fixed-30 selection, spatial robustness, and training.
- `scripts/`: the reproducible image reconstruction, measurement, figure-generation, and Word-draft builders.
- `qa/`: completeness checks for the 120-step comparison and the nine-pillar CD analysis.

## Verified structure identity

- The 50× acquisition keeps the sample orientation; the center-facing pillar block is upper-right of the sample-center junction.
- The 20× acquisition is vertically flipped relative to 50×; the center-facing pillar block is lower-right.
- Both corrected pillar crops are dark-on-bright. The former 20× bright-circle crop was a via region and is not used.
- Every three-way comparison uses the same image frame, pillar centers, and adjacent-frame pair.

## Primary displacement population

The experiment intentionally recorded about 50 frames per condition as backups for occasional PI motion errors. The thesis population locks exactly 30 steps per sequence, for 120 steps total.

Selection has two stages:

1. Exclude cross-session steps, Raw motion beyond the 25% command tolerance, and pairs without complete nine-pillar measurements in all three methods.
2. Rank the remaining candidates only by Raw two-dimensional local-motion deviation and keep the best 30. No Wiener or MOSR outcome is used for ranking.

The four usable candidate counts are 48, 48, 32, and 49; each contributes exactly 30 steps. All 120 selected steps contain all nine pillars and no missing primary values.

## Headline results

- Pooled command MAE: Raw 9.54 nm, Wiener 7.46 nm, MOSR 6.74 nm.
- Pooled within-grid inconsistency: Raw 17.63 nm, Wiener 7.92 nm, MOSR 6.47 nm.
- Steps with lower within-grid inconsistency than Raw: Wiener 103/120; MOSR 107/120.
- Median 10–90% edge width at 50×: Raw 620.1 nm, Wiener 467.7 nm, MOSR 508.5 nm.
- Median 10–90% edge width at 20×: Raw 802.2 nm, Wiener 493.1 nm, MOSR 246.1 nm.
- Median per-pillar CD bound width across 35–65% thresholds and two profile modes: Raw 354.5 nm, Wiener 429.6 nm, MOSR 143.3 nm. The per-pillar chart shows only lower and upper bounds, with no central operating point for Raw, Wiener, or MOSR.
- Threshold-robust median CD error: Raw 95.33 nm, Wiener 123.71 nm, MOSR 76.11 nm. The Wiener 50% advantage is therefore threshold-specific.

## Interpretation limits

- The nominal PI command is a consistency reference, not independent stage-position truth.
- The SEM-anchored CD comparison uses one 50× static image and nine identified pillars.
- The stronger Wiener setting creates visible ringing. Higher contrast and narrower edges do not automatically prove distortion-free CD recovery.
- No positive monotonic worsening with PSF-calibration distance was found over the sampled region; this does not prove that the full field is spatially invariant.

## Reproduction order

Run the base MOSR figure builder, build the fixed Wiener dataset, audit its displacement sequence, compute the three-way results, and then run the final MATLAB figure builder. The final checks require 120 locked steps, nine valid pillars in every primary measurement, 9/9 valid CD crossings, 42 threshold-summary rows, and complete spatial-robustness tables. The Word builder can then create the updated Section 6.2 draft from the regenerated figures and tables.
