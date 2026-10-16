# R72 R61 Synthetic Defect ACM Contour Validation

This experiment applies the same MATLAB Chan-Vese ACM family used by the R69/R70 SEM contour studies to the twenty held-out synthetic `edge_defects` images reconstructed in R71.

The primary result is a shape-only comparison after translation alignment. Fixed-coordinate results are retained separately so position error is not hidden. The report also includes COMBO as an older reference and three ACM parameter presets as a robustness check.

## Run

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' scripts\run_r72.py --stage all --force-acm
```

After the first complete run, omit `--force-acm` to reuse the frozen ACM masks and regenerate only analysis, figures, report, and tests.

## Outputs

- `results/tables`: image-level contour measurements, paired statistics, and sensitivity summaries.
- `results/masks`: the extracted truth, Raw, COMBO, and R61 binary masks.
- `results/figures`: contour overlays, metric comparisons, failure cases, and robustness checks.
- `reports/R72_RESULTS_TW.md`: the plain-language scientific conclusion.
