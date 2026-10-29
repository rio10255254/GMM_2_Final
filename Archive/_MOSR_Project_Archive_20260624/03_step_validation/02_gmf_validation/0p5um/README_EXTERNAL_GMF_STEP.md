# step_0p5um Step External GMF Validation Package

This package is prepared for external GMF validation.

- Source audit root: `Step_analysis_20260623/clean_step_audit_from_original_pos5_0p5um_20260623_2352`
- Source manifest: `Step_analysis_20260623/clean_step_audit_from_original_pos5_0p5um_20260623_2352/selected_0p5um_positions.csv`
- Expected adjacent step: `0.5 um`
- Camera pixel / objective: `2.5 um / 20x`
- Object-plane pixel size: `0.125000 um/px`
- Expected adjacent step in image: `4.000000 px`

Important: the original Step capture has two frames at each commanded position.
This package splits them into `rep0` and `rep1` folders so every GMF case is a
clean monotonic motion sequence. Do not run GMF on an interleaved two-replicate
folder unless the downstream analysis explicitly handles same-position repeats.

Use `paths_for_gmf_tool.tsv` as the external-GMF input table. The expected
output folders are already created under `_gmf_scores/<case>`.
