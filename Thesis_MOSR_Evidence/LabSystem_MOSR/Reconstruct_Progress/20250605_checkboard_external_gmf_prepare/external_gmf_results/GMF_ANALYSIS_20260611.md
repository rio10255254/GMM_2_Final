# 20250605 Checkboard External GMF Analysis

Generated: 2026-06-11T20:55:00+08:00

## Inputs

- External GMF text folder: `external_gmf_results/`
- Compared cases: raw input, Lab R39/R40 latest, and Lab R39/R40 tradeoff
- Object-plane pixel size: `0.172500 um/px`
- Expected 1 um step: `5.797101 px`
- Standard deviation: population standard deviation, matching the previous Lab GMF report

## Headline Result

| Case | Rows | Mean step (px) | step_std full (px) | step_std um | vs raw | Min score |
|---|---:|---:|---:|---:|---:|---:|
| Lab R39 tradeoff | 50 | 5.830163 | 0.254427 | 0.043889 | -2.39% | 98.8012 |
| Lab R40 latest | 50 | 5.830061 | 0.255399 | 0.044056 | -2.02% | 99.5636 |
| Lab R40 tradeoff | 50 | 5.830041 | 0.255418 | 0.044060 | -2.01% | 94.3381 |
| Lab R39 latest | 50 | 5.830673 | 0.257648 | 0.044444 | -1.16% | 99.8133 |
| Raw input | 50 | 5.831306 | 0.260669 | 0.044965 | baseline | 99.9026 |

## Diagnostic: Shared Abnormal Interval Removed

The shared abnormal interval is step 19: `Image__2026-06-05__16-07-42.bmp` -> `Image__2026-06-05__16-08-18.bmp`.

| Case | Step at shared interval (px) | step_std without it (px) | vs raw without it |
|---|---:|---:|---:|
| Lab R39 tradeoff | 7.431 | 0.107612 | -1.66% |
| Lab R40 tradeoff | 7.437 | 0.108066 | -1.25% |
| Raw input | 7.474 | 0.109431 | baseline |
| Lab R40 latest | 7.431 | 0.109906 | +0.43% |
| Lab R39 latest | 7.437 | 0.113533 | +3.75% |

## Interpretation

The new tradeoff files change the conclusion. R39 tradeoff is now the best case both on the full series and after the shared abnormal interval is removed. R40 tradeoff is also better than raw after that interval is removed.

The shared abnormal interval remains in every case, so it should still be treated as a capture/sequence issue rather than a reconstruction-specific failure.

## Files Written

- `analysis_summary.json`
- `analysis_summary.csv`
- `step_diagnostics.csv`
- `gmf_step_std_comparison.png`
