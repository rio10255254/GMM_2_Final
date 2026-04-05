# R37 Frequency-Dependent PSF Regularization Results (2026-04-06)

## Candidate: r37_freqreg_p95
- PSF_FREQ_REG_ENABLE=True, sigma=0.15, lo_mult=2.0, hi_floor=0.3
- ROBUST_LOSS_PERCENTILE=0.95, WARMUP=10
- Best epoch: 21

## Result: FAILED — worse than R33 on all metrics

| Metric (0.8px) | R30 | R33 hard_p95 | R37 freqreg |
|----------------|-----|-------------|-------------|
| step_std_y | 0.205 | **0.129** | 0.138 |
| outer res_std | 2.599 | 2.905 | 3.876 |
| inner res_std | 2.894 | 2.684 | 3.283 |
| gradient mag | 3.46 | 2.36 (-32%) | 2.29 (-34%) |
| Laplacian | 1.86 | 0.98 (-47%) | 0.94 (-49%) |
| 8px k2 | stable | moderate | volatile_risk |

## Root Cause

Lowering reg at high frequencies (3 vs 10) makes Wiener deconvolution more
aggressive at HF, but this amplifies HF noise in the deconvolved input.
The encoder then receives a noisier signal, producing more gradient outliers,
which Winsorize has to cap more aggressively → net result is softer, not sharper.

The learnable freq_reg parameters (sigma/lo_mult/hi_floor) converge to a regime
where the physics layer produces similar or worse input quality than uniform reg=10.

## Conclusion

Frequency-dependent regularization in the physics layer does NOT break the
sharpness-stability trade-off. The Wiener deconvolution's HF noise amplification
makes aggressive HF deconvolution counterproductive.

R33 hard_p95 remains the best variant across all experiments (R33-R37).
