# 2026-09-24 20× center-nine pillar PSF calibration

## What was fitted

The 25 BMP files in `D:\GMM_2_Final\20260924` are a 5×5 set of views of the same physical nine pillars near the sample-center junction. All source files remain in place. The camera exposure in `snapshots.csv` is 3000 µs for every frame. The median observed pillar pitch is about 29.0 pixels, consistent with the existing 20×, 3.45 µm camera-pixel, 5 µm pillar-pitch calibration.

The SEM reference is the **pillar** radius table in `Thesis_MOSR_Evidence/SEM_data/via_pilar.xlsx`, sheet `SEM data`, cells `J8:L10`. The optical pillar block is dark circles on a bright background in these images; the nearby bright circles on a dark background are vias and were not used. The existing July 20× center-nine calibration supplies the working orientation. In image row order, the nine corresponding SEM pillar IDs are:

| Image row | Left | Middle | Right |
|---|---:|---:|---:|
| Top | 36 | 30 | 24 |
| Middle | 35 | 29 | 23 |
| Bottom | 34 | 28 | 22 |

`sem_9_mapping.csv` gives each ID's exact workbook cell, SEM diameter and original P-image file. These are working **per-pillar** identities inherited from the July orientation; the 36-pillar SEM file ordering itself was verified previously. Neither image appearance nor fitted PSF score was used to choose an SEM permutation.

## Localization and fitting

The July 20× reference photo was matched to the middle new photo, and all 25 new views were linked through their 40 neighboring overlaps. The July-to-middle match had 117 inliers; maximum 5×5 loop disagreement was 0.236 pixel. All 225 pillar locations were checked against dark-circle contrast. The recorded location table uses MATLAB one-based image coordinates. The nine extracted spots were centered to within 0.231 pixel of their intended fitting positions.

The existing `build_center_9pillar_fit_pair.m` assembled nine local patches from each source image into a 301×301 fitting image. The existing `HDR_fitting_2D_WholeFOV_reasonable_v1.m` and BADS fitted the PSF to SEM-diameter disks. These are nine-pillar crops, rather than full-frame fits. A named bound-scale option was added to the existing fitter; its default is 1, preserving prior behavior.

The original coefficient bounds caused many parameters to stick at their limits. We fitted six pillars and reserved IDs 36, 29 and 22 for validation on frames 1, 13 and 25. Brightness was estimated on the six training pillars and then checked on the three reserved pillars. Mean reserved-pillar squared error was 0.004348, **0.002412**, 0.003292 and 0.004040 for bound scales 1, 2, 4 and 8 respectively. Scale 2 was best on every one of the three frames. The final 25-image fit therefore uses scale 2, independent starts, locked tilt, and the original BADS objective. `bound_cv_summary.csv` contains each comparison.

## Deliverables

- `PSF_20260924_center9_25_normalized.mat`: 25 unit-sum PSFs in a 5×5 image-order grid, plus separately estimated brightness factors and source names.
- `psf_grid_25.png`: same-scale view of the 25 fitted PSFs.
- `forward_fit_example_13.png`: new photo and forward-model comparison for the middle view.
- `final_fit_qa.csv` and `final_fit_qa_summary.json`: every image's fit and PSF checks.
- `center9_locations.csv`, `center9_25_frames.png`, `sem_9_mapping.csv`: position and SEM correspondence evidence.
- `source_sha256.csv`: hashes of the 25 original images, capture log, SEM workbook and 36-pillar map.
- `fit_wide2/`: raw BADS output and its exact configuration. The normalized MAT file above is the practical PSF-only output; raw fitted kernels also contain a brightness multiplier.
- `diagnostics_pre_coordinate_fix/`: clearly marked invalid preliminary runs made before fixing a one-pixel coordinate-origin mismatch. **Do not use those PSFs.**

## Results and limits

All 25 BADS fits completed, and all 25 normalized PSFs are finite, nonnegative, centered, and clear of the kernel edge. With each photo's brightness adjusted separately, the median forward-model squared error is **0.003108** for the new PSFs versus **0.005266** for the existing July PSF. The new PSF is closer on all 25 fitting photos; median image correlation changes from **0.9508** to **0.9705**. These 25 comparisons reuse the fitted nine pillars, so the reserved-pillar check above is the evidence that the wider bounds generalize within this sample.

The 25 PSF shapes are similar: neighboring fitted kernels have correlation at least 0.9985. This dataset does not establish a strong spatial change in PSF shape. Source-hash and output verification passed for 28 source files, 225 pillar locations, 25 fits and 25 normalized kernels; see `verification.json`.

The recovered PSF is an empirical forward-model fit for this optical session and these nine pillars. In the final fits, 7–10 of 12 free wavefront coefficients approach their manually chosen bounds; they should not be interpreted as uniquely measured physical aberrations. SEM disks use the existing diameter table rather than full SEM contours. Reserved-pillar validation tests nearby pillars on the same specimen; it does not establish independent-sample accuracy or deconvolution performance. The nominal object-pixel scale is 0.1725 µm/pixel.

## Reproduce

From this folder, run `register_center9.py`, then MATLAB `run_20260924_center9('prepare')`, MATLAB `run_bound_cv()`, `summarize_bound_cv.py`, MATLAB `run_20260924_center9('fit_wide2')`, `finalize_fit.py`, and `verify_deliverable.py`. The original photos and SEM files are read, not overwritten.
