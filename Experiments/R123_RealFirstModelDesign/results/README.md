# R123 outputs and limits

These are design-support artifacts, not trained-model results.

- `real_source_inventory.csv` / `real_panel_audit.json`: actual input inventory and replayed historical real measurements.
- `historical_real_paired_*.csv`: old R109/R119 measurements recomputed at the stated paired levels; no new model predictions.
- `real_input_panel.png`: actual raw inputs only.
- `real_baseline_replay.png`: historical comparison only.
- `operator_math_checks.json`: limited numerical checks, not calibration or real performance.
- `initial_design_review.json`: preserved initial draft and identified flaws.
- `protected*.json`: exact inputs read by this round; not replacements for historical expectations.
- `design_verification.json`: consistency, source integrity and declared limits.

All outputs are small; retain the full directory locally. Raw inputs are referenced in place, not duplicated. No checkpoints or training sets were created. The 144 frozen full-field ROIs are not the old 144-scene confirmation set; they are legacy Raw-selected regions of existing real development sequences.
