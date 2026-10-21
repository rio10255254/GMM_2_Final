# R150 Validation Plan

1. Verify the shared R149 manifest, base data, overlay counts and absence of real/SEM/PI training answers.
2. Verify full/tiled equality, constant-image behavior, dependency margin, mean-only model operator and nonzero training gradients.
3. Verify the two exact-design R149 controls and one R150 64-update smoke run.
4. Freeze source, data, PSF and launcher hashes.
5. Run one 8,192-update scratch model with the global boundary objective.
6. Run the unchanged 930-frame/8,370-circle real evaluation and complete-scan paired comparisons.
