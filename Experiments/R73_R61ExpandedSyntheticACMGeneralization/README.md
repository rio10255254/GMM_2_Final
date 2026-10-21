# R73 Expanded Synthetic ACM Generalization

This experiment expands R72 from one closed-defect family to five newly generated, single-object microscopy contour families. Every image has an exact geometry mask, a clean rendered truth image, a degraded raw image, and a frozen R61v16 reconstruction.

The exact geometry mask is the primary reference. MATLAB Chan-Vese ACM is used to extract the Raw and R61 contours, while ACM on the clean truth image is retained as an extraction-quality audit. No scale or rotation fitting is allowed.

The original fixed outer seed was rejected because it remained unconverged on five deep-crescent clean images even after 1,400 iterations. A polarity-independent automatic inner seed was then calibrated only on clean rendered images. It finds the largest valid non-border object from both bright and dark Otsu candidates and erodes it by three pixels; it never reads the exact mask. A 15-image pilot achieved a worst clean-image IoU above 0.994 at 100 iterations. All model comparisons freeze that rule and iteration count, while the sensitivity check varies only contour smoothing.

## Run

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' scripts\run_r73.py --stage all --force-generate --force-acm
```

After the first complete run, omit the force flags to reuse the frozen dataset, reconstructions, and ACM masks.

## Main outputs

- `reports/R73_RESULTS_TW.md`: plain-language scientific result.
- `results/figures`: reconstruction and complete-contour comparisons.
- `results/tables`: image-level ACM measurements, paired statistics, and robustness checks.
- `results/decision.json`: frozen gate result and interpretation boundary.
