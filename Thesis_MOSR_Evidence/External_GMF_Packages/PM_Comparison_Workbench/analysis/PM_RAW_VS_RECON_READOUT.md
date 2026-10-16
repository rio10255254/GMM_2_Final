# PM raw-versus-reconstruction readout

Date: 2026-09-02

The common Raw PM result is `reference/raw/PM_score.txt`. Each model's
`txt_out/PM_score.txt` is treated as that model's reconstruction result. All
six files contain 100 usable coordinate rows, covering `frame_0001` through
`frame_0100`, with no duplicate frame numbers.

The Raw trajectory moves about `-794.530 px` in Y over the 99 intervals. The
numbers below are from the external PM output only; they are not a replacement
for ACM contour or visual microscopy checks.

| model | Y step jitter | change vs Raw | Y straight-line residual | change vs Raw | Y step RMSE vs Raw | PM score mean | score change |
|---|---:|---:|---:|---:|---:|---:|---:|
| Raw reference | 0.074303 | — | 0.091599 | — | — | 97.234201 | — |
| R104E48 | 0.075406 | +0.001103 | 0.092569 | +0.000970 | 0.018668 | 97.204587 | -0.029614 |
| R103E48 | 0.077697 | +0.003394 | 0.092880 | +0.001281 | 0.022134 | 97.784448 | +0.550247 |
| V42E120 | 0.074323 | +0.000020 | 0.094630 | +0.003031 | 0.032067 | 99.096871 | +1.862670 |
| R61v11 | 0.090044 | +0.015742 | 0.100141 | +0.008542 | 0.057831 | 99.453802 | +2.219601 |
| R109E48 | 0.096343 | +0.022040 | 0.104654 | +0.013055 | 0.059924 | 97.854071 | +0.619870 |

## Reading the result

- V42E120 preserves the Raw frame-to-frame Y stability almost exactly, while
  also raising the PM score substantially.
- R104E48 changes the measured motion the least. Its step error and straight
  line residual are the smallest, but its PM score is essentially unchanged.
- R103E48 is also close to Raw in motion stability and has a modest score gain.
- R61v11 has the highest PM score, but its frame-to-frame jitter is visibly
  larger than Raw, so the high score should not be read as better displacement
  stability by itself.
- R109E48 does not win this PM test: its Y jitter and straight-line residual are
  the largest of the five candidates.

The absolute coordinate differences are mostly fixed offsets rather than drift:
after removing the mean offset, the Y difference spread is only about
0.014–0.083 px across the five models. Therefore the larger absolute Y RMSE
(roughly 16–29 px) mainly reflects a changed coordinate origin/template match,
not a 16–29 px frame-to-frame instability.

The complete machine-readable outputs are:

- `pm_raw_vs_recon_comparison.json`
- `pm_raw_vs_recon_comparison.csv`
