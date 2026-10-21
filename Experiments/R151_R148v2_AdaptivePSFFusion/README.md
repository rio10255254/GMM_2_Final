# R151 — R148v2 Adaptive Fourier PSF Fusion

## Status

Architecture restoration and executable preflight are complete. This is not a formal trained model and does not replace R148v2. A full 8192-update run was deliberately not started because the current 25-PSF data did not pass the predeclared selector-identifiability probe.

## What was restored

- FFT of the observed image.
- The complete latest 25-PSF bank.
- A feature-conditioned softmax weight estimator.
- Weighted fusion of candidate inverse filters.
- One iFFT after algebraically equivalent frequency-domain fusion.
- A bounded learnable residual scale and direct residual connection.
- R148v2 one-pass context U-Net, three independent native-resolution stages, input anchor, anti-aliasing and 512/24 tiled inference.

The selector now reads the R148v2 context features plus radial frequency statistics. The PSF origin is corrected before FFT, the old zero final-layer initialization is removed, known synthetic PSF identity and physical width/halo descriptors have explicit training signals, and the residual scale cannot silently become exactly zero.

## Verified entry points

- `scripts/preflight.py`: wiring, gradients, candidate sensitivity, fusion equivalence and tiled/full check.
- `scripts/smoke_real_frame.py`: one native 1544×2064 real-frame execution and memory check.
- `train.py --run-name <name> --short-updates <n> --seed <seed>`: resumable short training only.
- `reports/R151_DESIGN_AND_PREFLIGHT.md`: full reason, evidence, limits and promotion gates.

Do not start formal training until the selector-identifiability gate in the report is satisfied by a more informative PSF/data condition or by known capture metadata.
