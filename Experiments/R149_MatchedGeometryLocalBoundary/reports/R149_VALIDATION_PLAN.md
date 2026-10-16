# R149 Validation Plan

1. Verify all base hashes, 96 overlay parents, requested geometry ranges and zero use of real/SEM/PI answers.
2. Check full/tiled equality, constant-image behavior, local center/radius gradient direction and translation consistency.
3. Run global/local matched controls at two fresh seeds for 512 updates each.
4. Freeze the exact source set only after the gate passes.
5. Run one 8,192-update scratch model with the local objective.
6. Evaluate the fixed 30 scans, 930 images and 8,370 circles without model-dependent frame selection or post-processing.
7. Report complete-scan paired intervals and preserve unfavorable size, worst-case and runtime results.
