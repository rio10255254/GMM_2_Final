# R117 Center-Locked Subpixel Scratch

R117 is an independent, single-image MOSR experiment trained from random
initialization.  It keeps R116's local and tile-safe operating contract but
keeps a smaller, independently trained normal-warp path because the frozen E42
causal test showed that removing it damages all 36 physical SEM pillars.  Edge
width and evidence detail are projected around the predicted contour so they
can sharpen an edge without adding a second, uncontrolled center displacement.

The paired synthetic views are supervision only.  Each translated target is
rendered from the 8x latent geometry before final area downsampling; the model
still accepts one image at deployment.  No SEM, HS100MG, V42, R61, R109, or
R116 pixels or weights are used for training.

Run order:

1. `scripts/prepare_data.ps1`
2. `scripts/smoke_test.ps1`
3. `scripts/start_formal_training.ps1`
4. `scripts/monitor_training.ps1`

Formal selection uses shape, internal displacement stability, visible detail,
identity, and tile safety.  External GMF is intentionally outside the thesis
selection rule.
