# R105A Geometry Renderer Falsification

This is a mechanism experiment, not a new production model.

## Question

R104 already predicts a signed-distance field, but its final reconstruction is still Raw plus four image residuals. R105A tests the one mechanism that was designed but never completed as an actionable output: the signed-distance zero level set directly renders the final monotonic subpixel boundary.

## Matched comparison

The residual and renderer arms use:

- the same procedural samples;
- the same backbone and auxiliary heads;
- the same seed and initialization;
- the same optimizer, steps and batch order;
- the same SDF, transition-width and intensity-level supervision.

All geometry and continuous edge labels are formed at 4x resolution and only then area-downsampled. The first low-resolution-SDF pilot is retained under `archive/pilot_lowres_sdf_20260824` and is not used for the decision.

The clean 600-step run remained visibly unconverged for the renderer, so it is preserved under `archive/supersampled_0600step_20260824`. The deciding run trains both matched arms from scratch for 1,800 steps.

Only the final image formation differs.

## Decomposition

1. Oracle SDF, width and levels.
2. Learned SDF with true width and levels.
3. Learned SDF and width with true levels.
4. Fully learned renderer.
5. Matched image-residual baseline.

## Interpretation

If the renderer does not improve boundary center, transition width and halo together, this line is falsified and no full R105 should be trained. Real SEM, HS100MG and external GMF data are not training inputs.

## Final status

The clean 1,800-step matched run is complete. The renderer improved transition width and reduced halo, but it moved the boundary center and was worse on contour distance, centroid, identity behavior, exposure consistency and tiled/full agreement. Neither a fixed source-to-renderer blend nor a residual-to-renderer blend rescued the held-out shapes. A formal R105 was therefore not started.

The final Chinese findings are in `reports/R105A_FINAL_FINDINGS_ZH.md`.

Run all probes with:

    C:\Users\Rio\anaconda3\python.exe scripts\run_all.py
