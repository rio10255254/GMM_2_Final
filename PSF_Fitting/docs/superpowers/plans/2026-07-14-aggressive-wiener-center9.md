# Aggressive Wiener Center-9 Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the over-smoothed 20x and 50x center-nine deconvolution evidence with one fixed aggressive Wiener setting that makes edges narrower while moving apparent CD toward SEM.

**Architecture:** Keep the fitted PSFs and exact captured crops unchanged. Apply MATLAB `deconvwnr` with a fixed scalar NSR of 0.08 to both magnifications, then use one unchanged half-contrast CD rule before and after. Add explicit edge-width and ringing measurements so a smaller CD alone cannot be mislabeled as restoration.

**Tech Stack:** MATLAB R2025b Image Processing Toolbox, Python 3.12, SciPy, NumPy, Matplotlib, Pillow.

---

### Task 1: Add a failing acceptance test

**Files:**
- Create: `D:\GMM_2_Final\PSF_Fitting\tests\python\test_center9_wiener_evidence.py`
- Read: `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\tables\center9_pillar_fit_20x_50x\cd_before_after_summary.csv`

- [ ] Write a test requiring exactly two finite summary rows (`20x`, `50x`), selected NSR exactly `0.08`, `edge_width_change_percent < 0`, `mae_change_percent < 0`, zero inverted centers, and all expected output figures readable.
- [ ] Run `python -m pytest tests/python/test_center9_wiener_evidence.py -q` and confirm it fails because the current summary lacks the sharpening fields and the 50x result is over-smoothed.

### Task 2: Replace the conservative Wiener selection

**Files:**
- Modify: `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\psf_deconvolution_cd\run_wiener_deconvolution.m`

- [ ] Replace the no-ringing selector with fixed NSR `0.08` for both 20x and 50x.
- [ ] Keep fitted PSF normalization, symmetric padding, unclipped numeric output, and 8-bit standalone PNG/BMP output unchanged.
- [ ] Save the noise-estimated NSR and the selected aggressive NSR in each numeric result.
- [ ] Remove candidate-NSR arrays and the obsolete “stable NSR” selector metadata so no old selection rule survives in the MAT files, CSV files, or manifest.

### Task 3: Measure real sharpening and CD movement

**Files:**
- Modify: `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\psf_deconvolution_cd\analyze_cd.py`

- [ ] Add per-pillar edge-transition width: sample 360 radial traces at 0.05-pixel spacing; smooth each trace by 0.30 px; use the same robust core/background levels as CD; linearly interpolate the 10% and 90% dark-to-background crossings; require at least 90% valid traces; use the median angular width in pixels.
- [ ] Add radial ringing ratio as inward-dip magnitude divided by outward-rise magnitude on the median normalized profile, and define no inversion as `core_level < background_level` for every dark pillar.
- [ ] Extend the per-pillar and summary CSV files with raw/deconvolved edge width, edge-width change, ringing, and polarity fields.
- [ ] Define summary edge change from the two nine-pillar mean widths: `100 * (mean_deconvolved_width / mean_raw_width - 1)`.
- [ ] Add one standalone edge-width comparison chart per magnification.
- [ ] Reject missing, infinite, or NaN measurements before writing tables.
- [ ] Stop loading candidate-NSR fields in `analyze_cd.py`; rename all CSV and manifest fields from “stable NSR” selection to fixed aggressive NSR `0.08`.

### Task 4: Regenerate and verify artifacts

**Files:**
- Regenerate: each magnification's `09` through `14` figures.
- Regenerate: detailed, summary, and threshold-sensitivity CSV files.

- [ ] Run the MATLAB deconvolution script.
- [ ] Run the Python analysis script.
- [ ] Run the acceptance test and confirm both magnifications sharpen and improve CD with fixed NSR `0.08`.
- [ ] Verify exactly 14 regenerated image files: 12 PNG files (`09` through `14` for both magnifications) plus 2 BMP files (`09` for both magnifications).
- [ ] Open and inspect every regenerated PNG (`09` through `14`) for both magnifications; verify no center inversion, clipped labels, or misleading scaling.
- [ ] Verify all images load and the tables contain exactly 18 detailed rows, 2 summary rows, and 6 threshold-sensitivity rows.
