# R69 ACM Contour SEM Validation

This experiment tests whether the frozen R61v16 PSF-off reconstruction makes the full non-circular pillar contour closer to the paired SEM contour than the optical input.

The primary analysis uses the twelve exposure levels in `image_cropped/13.bmp` through `24.bmp`, because the legacy alignment record maps those exact optical images to the nine P-series SEM images and their center-36 pillar identities. The 2026 50x displacement reconstruction is audited separately because matching the target design is not, by itself, proof of the same physical specimen and pillar identities.

## Result

Conditional pass. R61v16 improves the main full-contour agreement for all 36 pillars in exposure images 13 through 22, but worsens all 36 in the two darkest images 23 and 24. Perimeter and circularity errors also worsen, so the evidence supports improved coarse outer-boundary placement under adequate exposure, not universal or fine-edge shape fidelity. See `reports/R69_RESULTS_TW.md` for the thesis-facing interpretation.

Primary contour extraction uses MATLAB `activecontour` with the Chan-Vese method. Each optical contour is translation-aligned to the corresponding SEM contour only; no per-pillar scale or rotation fitting is allowed. The reported measures compare overlap, mean symmetric boundary distance, 95th-percentile boundary distance, area, perimeter, and circularity without fitting a circle or radius.

## Run

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' scripts\run_r69.py --stage all
```

The default complete run verifies the paired source copies and the twelve reconstructions, reuses already validated ACM tables, regenerates the statistics and figures, and runs the automated checks. Add `--force-acm` only when the contour extraction settings change and the full heavy extraction should be recomputed.

## Outputs

- `results/tables`: per-pillar measurements and paired summaries.
- `results/figures`: SEM/raw/reconstruction contour overlays and comparison figures.
- `reports/R69_RESULTS_TW.md`: thesis-facing conclusion and limitations.
