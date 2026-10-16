# Displacement Algorithms

This folder collects two thesis-safe displacement measurement routes that can
replace proprietary external GMF checks during local analysis.

## Folder map

- `phase_correlation_dft/legacy_matlab/`
  - Original MATLAB DFT/subpixel registration files found under
    `D:\NonSystemFiles\GMM`.
  - Use this family as the main intensity-based displacement estimator.
- `feature_corner_geometry/legacy_matlab/`
  - Original MATLAB corner, checkerboard, circle-center, and geometry alignment
    scripts found under `D:\NonSystemFiles\GMM2`.
  - Use this family as an independent anchor-based cross-check.
- `scripts/measure_phase_dft.py`
  - Clean Python entry point for DFT phase-correlation displacement.
- `scripts/measure_feature_anchor.py`
  - Clean Python entry point for corner tracking, circle-center tracking, or
    checkerboard-center tracking.
- `scripts/measure_shape_edge_anchor.py`
  - Shape-aware edge/chamfer anchor tracker. This route uses boundary-only
    edge maps for subpixel motion and validates the result with local shape
    matching. It is intended for thesis checks where model boundary quality
    should matter more than raw texture similarity.

## Fast commands

Current 20260702 100MG displacement data with interactive ROI selection:

MATLAB Run button workflow:

1. Open `D:\GMM_2_Final\Tools\Displacement_Algorithms\Run_20260702_100MG_PhaseDft_SelectROI.m` in MATLAB.
2. Press Run.
3. Draw the ROI on each sequence's first image and confirm it.

The MATLAB workflow writes outputs to:

- `D:\GMM_2_Final\20260702_100MG_phase_dft_analysis_matlab`

For this 20260702 100MG dataset, the MATLAB workflow uses 0.069 um/pixel
for physical-unit conversion, matching Basler 3.45 um camera pixels at 50x.

PowerShell/Python workflow:

```powershell
PowerShell -ExecutionPolicy Bypass -File D:\GMM_2_Final\Tools\Displacement_Algorithms\Run_20260702_100MG_PhaseDft_SelectROI.ps1
```

The interactive launcher uses the DFT phase-correlation route, scans:

- `D:\GMM_2_Final\20260702_100MG_位移`

and writes outputs to:

- `D:\GMM_2_Final\20260702_100MG_phase_dft_analysis`

It will process sequence folders such as `x_0.5um` and `x_1um`. ROI selections
are saved in `selected_rois.json`, so the same ROI can be reused.

DFT phase correlation:

```powershell
python D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts\measure_phase_dft.py `
  --input D:\GMM_2_Final\Step `
  --output-csv D:\GMM_2_Final\Tools\Displacement_Algorithms\tests\phase_steps.csv `
  --output-json D:\GMM_2_Final\Tools\Displacement_Algorithms\tests\phase_summary.json `
  --reference both `
  --upsample-factor 100
```

Feature/corner tracking:

```powershell
python D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts\measure_feature_anchor.py `
  --input D:\GMM_2_Final\Step `
  --output-csv D:\GMM_2_Final\Tools\Displacement_Algorithms\tests\corner_steps.csv `
  --output-json D:\GMM_2_Final\Tools\Displacement_Algorithms\tests\corner_summary.json `
  --method corners
```

Shape-aware edge anchor tracking:

```powershell
python D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts\measure_shape_edge_anchor.py `
  --input D:\GMM_2_Final\Thesis_MOSR_Evidence\External_GMF_Packages\best_displacement_models_20260706\trusted_full_sequences\100MG_x_1um_full_raw `
  --output-csv D:\GMM_2_Final\Tools\Displacement_Algorithms\tests\shape_edge_steps.csv `
  --output-json D:\GMM_2_Final\Tools\Displacement_Algorithms\tests\shape_edge_summary.json `
  --expected-dx-px -14.492754 `
  --expected-dy-px 0 `
  --search-radius-px 3 `
  --edge-quantile 0.74
```

Optional ROI crop format:

```text
--crop x,y,width,height
```

## Output meaning

- `dx_px`, `dy_px`: displacement from the reference image to the current image.
- `cumulative_dx_px`, `cumulative_dy_px`: accumulated displacement over the
  ordered sequence.
- `std_dx_px`, `std_dy_px` in JSON: step-to-step stability values.

## Recommended use

Use `measure_phase_dft.py` as the primary open displacement number. Use
`measure_feature_anchor.py --method corners` on the same ROI as a second view.
Use `--method circle` only as an auxiliary check when the ROI contains one clear
circle or ring; it is not robust on a full image with repeated structures. If
the sample is a checkerboard, run `--method checkerboard`.

Use `measure_shape_edge_anchor.py` when the comparison should emphasize whether
the reconstructed boundary itself became easier to localize. Give it the same
ROI and expected pixel step for Raw and every reconstruction. Treat
`match_score_px`, `overlap_fraction`, and failed steps as confidence checks;
do not claim a model win if the displacement improves but the shape confidence
gets worse.
