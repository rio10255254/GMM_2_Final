# R149 Methodology

## Question

Can real-scale synthetic circle geometry and non-cancelling local boundary supervision retain R148v2's best-in-set diameter repeatability while reducing the systematic size bias and improving short-step localization?

## Controlled changes

1. 96 dense parents are replaced by procedural circle configurations covering 6–12 px radius and 24–36 px pitch. The split counts remain 512/128/128 and the training budget remains 8,192 updates.
2. The model receives the fixed mean PSF for every training and inference image. Individual measured PSFs still form the blurred inputs but are not supplied as per-image identities.
3. Boundary supervision uses the local-cell coordinate error at weight 0.35. Each 96 px supervised core is divided into 12 px cells; target edge strength weights the cells. A preserved first pilot using weight 0.20 and a 25% global/75% local mix improved the common local score by only 0.75%, below the preset 3% gate, so it was not released to formal training.

Everything else remains the R148v2 design: one context pass, three independent native stages, source-referenced residual output, measured PSF bank, deterministic FP32 training, shift/photometry/noise coverage, optimizer, learning-rate schedule and final real-image protocol.

## Anti-leakage statement

The new circle centers, radii, polarity and photometry are generated from fixed random seeds. Real evaluation images, SEM sizes and PI positions do not enter training targets. SEM remains a same-sample evaluation reference only.

## Promotion rule

Results are ranked separately for short-step displacement, long-distance displacement, diameter repeatability, contour repeatability, same-sample SEM difference and runtime. No aggregate score can promote the model.
