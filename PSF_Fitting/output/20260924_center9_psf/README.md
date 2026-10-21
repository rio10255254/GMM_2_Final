# 2026-09-24 center-nine pillar PSF fit (20×)

## Programs actually used

- Organizer for these 25 captures: `D:\GMM_2_Final\PSF_Fitting\output\20260924_center9_psf\run_20260924_center9.m`.
- Existing nine-pillar crop and SEM target builder: `D:\GMM_2_Final\PSF_Fitting\build_center_9pillar_fit_pair.m`.
- Existing fit entry: `D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab\scripts\HDR_fitting_2D_WholeFOV_reasonable_v1.m`.
- Its optimizer implementation: `D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab\scripts\HDR_fitting_2D_WholeFOV_candidate_prealign.m`.
- BADS function called by that implementation: `D:\GMM_2_Final\PSF_Fitting\bads-1.1.3\bads.m`.

The actual fit uses 301×301 images assembled from nine local pillar patches, not the whole 2064×1544 camera frame. The named `aberration_bound_scale` option was added to the existing fit scripts while preserving their default at 1.

## Confirming these are P pillars and the correct nine identities

The P-pillar values come from `D:\GMM_2_Final\Thesis_MOSR_Evidence\SEM_data\via_pilar.xlsx`, worksheet `SEM data`, cells `J8:L10`. The 36-pillar numbering and source TIFFs are in `D:\GMM_2_Final\Thesis_MOSR_Evidence\SEM_data\ordering_result_20260729\SEM_center36_file_mapping.csv`. The original `H:\From_2TB_D_disk\13_thesis\matlab\ch4\SEMdataset\SEM2img_v2.m` pairs P SEM files with dark optical circles and V SEM files with bright optical circles. Thus the dark circles on a bright field in these photos are the P pillars used here; the bright circles on a dark field are vias and were excluded.

The current locked 20× source `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\01_CURRENT_THESIS_RESULTS_V42_CENTER9\config\sequence_center9_50x20x.json` lists these pillars in image row order:

| Image row | Left | Middle | Right |
|---|---:|---:|---:|
| Top | 36 | 35 | 34 |
| Middle | 30 | 29 | 28 |
| Bottom | 24 | 23 | 22 |

This is the vertical flip of the SEM `J8:L10` grid, not the rotation used by an earlier July PSF helper. We matched the current locked 20× source image directly to new frame `135148.bmp`: 91 inlier feature matches support the transform, and all nine transferred centers fall within **0.924 pixel** of the newly located pillars (pitch about 29 pixels). `current_20x_identity_transfer.json` records each center. `sem_mapping_audit.json` independently checks all nine IDs, Excel cells, numerical diameters and P TIFF filenames. The workbook and four P TIFF files used here also match the H-drive archive byte for byte. No fit score was used to select a permutation.

The 25 new frames are a 5×5 set of views of these same nine physical pillars. There are 225 located instances. The 40 adjacent-view links disagree by at most 0.236 pixel around the mosaic loops. The 301×301 prepared images place the pillar spots within about 0.29 pixel of their target centers. `center9_25_frames.png` shows all 25 selections; `center9_locations.csv` gives the MATLAB one-based locations.

## Bound selection and final fit

The original coefficient limits made many fitted parameters stick at a bound. We therefore used frames 1, 13 and 25 to compare bound scales 1, 2, 4 and 8, fitting six pillars and checking the other three (IDs 36, 29 and 22). After estimating brightness only from the six fitted pillars, mean error on the reserved three was **0.004731, 0.002351, 0.003141 and 0.003951**, respectively. Scale 2 was best on each of the three frames. The final run uses all nine pillars and all 25 frames, with scale 2, independent starts and locked tilt. The fitting procedure and BADS objective otherwise remain those of the existing program.

## Outputs

- `PSF_20260924_center9_25_normalized.mat`: the practical 5×5 bank of 25 unit-sum PSFs, source filenames, the nine SEM IDs and separately fitted brightness factors.
- `fit_wide2/`: unnormalized BADS output, coefficients, losses, and exact settings.
- `final_fit_qa.csv`, `final_fit_qa_summary.json`, `psf_grid_25.png`, `forward_fit_example_13.png`: per-frame checks and visual previews.
- `psf_center_audit.csv`, `psf_center_audit_summary.json`: independent peak, energy-centroid and edge-energy measurements for all 25 delivered PSFs.
- `sem_9_mapping.csv`, `sem_mapping_audit.json`, `current_20x_identity_transfer.json`: complete pillar and SEM evidence.
- `sem_shape_forward_validation/README_TW.md`: actual P-SEM contour forward-convolution check against matching new optical pillars, including held-out examples and the comparison with a simple Gaussian blur.
- `parameter_audit/README_TW.md`: end-to-end fitter and BADS-options audit. A separate gain-profiled 25-PSF research candidate improves held-out photo intensity agreement but slightly worsens edge and absolute-center measures; it has **not** replaced the delivered PSFs.
- `model_search/README_TW.md`: subsequent actual-SEM-contour and complete-pillar-image study. A separately packaged centered core-plus-halo PSF fitted by BADS passed a frozen six-frame, three-pillar check and predicts these photos better than the original BADS or one Gaussian; it is still marked **research only** and has not replaced the delivered PSFs.
- `source_sha256.csv`, `identity_source_sha256.csv`, `verification.json`: original-source, identity-source and output checks.
- `diagnostics_prior_orientation/` and `diagnostics_pre_coordinate_fix/`: earlier diagnostic runs explicitly marked invalid for delivery. Do not use those PSFs.

## What this establishes

All 25 corrected fits completed. On these fitting photos, the new normalized PSFs have median forward-model squared error **0.002864**, compared with **0.005602** for the prior July PSF after adjusting brightness for each photo; all 25 photos favor the new PSF. This comparison reuses the fitting pillars, so the reserved-pillar check above is the within-sample validation.

**PSF shift:** every delivered 101×101 PSF peaks exactly at pixel `(51,51)` in MATLAB coordinates, so peak shift is **0 pixel** across 25/25. Their energy centroid has median radial offset **0.184 pixel** and maximum **0.207 pixel**, equivalent to about **35.7 nm** at the nominal scale. The largest energy-center difference between any two PSFs is **0.227 pixel**. No PSF peak touches the array edge; the largest energy fraction in the outer three-pixel border is **0.0000833**. This is a small residual centroid offset, not an exactly zero energy-center shift. The prepared pillar spots themselves have at most about **0.288 pixel** center offset. A later position-sensitive reconstruction that switches between these PSFs should account for the individual kernel centroids.

The originally delivered kernels are empirical PSF fits for this acquisition and nine SEM-referenced pillars. The 25 images reuse the fitted nine pillars, while the reserved-pillar check gives a local test on unseen pillars in three representative frames. In the actual-SEM-contour forward check, this original PSF beats the July PSF on all nine held-out pillar appearances, but a simple Gaussian blur tuned on the six training pillars does slightly better on all nine. A later complete-pillar-image study found a separate centered core-plus-halo model that beats both on new held-out views; read `model_search/README_TW.md` and use only its research-labelled file for that model. Neither result verifies a unique physical PSF or deconvolution measurement improvement. In the original fits, 8–10 of 12 free wavefront coefficients still approach the manually set bounds, so they should not be treated as unique physical aberration measurements. The nominal image scale is 0.1725 µm/pixel.

## Reproduce and check

Run `register_center9.py`, MATLAB `run_20260924_center9('prepare')`, `audit_sem_mapping.py`, MATLAB `run_bound_cv()`, `summarize_bound_cv.py`, MATLAB `run_20260924_center9('fit_wide2')`, `finalize_fit.py`, `audit_psf_center.py`, then `verify_deliverable.py`. Original camera and SEM files are read, not overwritten.
