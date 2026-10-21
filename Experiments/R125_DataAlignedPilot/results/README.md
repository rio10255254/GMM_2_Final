# R125 evidence roles

Current data admission: `data_audit_v2.json`, all64scenes passing original limits and bound to `data/package_v2/manifest.json`. `data_audit_v1.json` remains rejected. Precision, representation-decomposition and intermediate-failure records remain intact.

Actual study: `runs/matrix_state.json` is the overall completed384-update matrix. Individual training summaries are preserved at the moment training ended and can still say real evaluation pending; the later matrix events and independent execution audits bind the actual completed evaluation. Do not read the training-only summary as the current full-pipeline state.

`real_*_step0000` / `real_*_step0064`:12actual fixed-panel evaluations; `real_comparison` aggregates one common population across all12. No qualification/promotion is implied. `execution_audit_independent_v2.json` is the strengthened final check; the original `execution_audit.json` is unchanged.

`training_reference_diagnostic`: post-start diagnostic on fixedfirstsixtraining scenes; not a holdout or a selection criterion. `real_photometry_scope.json`: post-pilot source-coverage warning; did not change training or metrics.

`report_snapshot.sqlite` and `data_fit_comparison.json` are transparent report-formatting adapters over verified JSON/CSV results. Their SQL was actually run because the report renderer requires query provenance; scientific measurements still come from the original scripts. `report_debug.html` and report-layout logs are debugging artifacts, not alternate deliverables. The single delivered reader is `reports/R125_REPORT.html`, using the official portable reader and verifier with a scoped Windows scrollbar/topbar layout fix. No report number, source or scientific check was altered for layout.

All generated data, failed versions, source traces, weights and model outputs are retained locally within the registered12GiB budget. Nothing from earlier experiments is deleted or rebaselined. Old 144-scene confirmation data were not evaluated.
