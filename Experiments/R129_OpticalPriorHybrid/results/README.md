# R129 results

Integration tests and initial failure are retained. Pilot training is four matched24-update runs; real outputs and SEM/motion tables are development diagnostics, not production qualification. Shared source data are referenced. Budget4GiB; retain source, plans, checkpoints, failures and representative figures on D.

- `figures/`: inspected comparison charts and fixed real-pillar example. `figure_sources.json` identifies sources.
- `real/`: all eight before/after methods, each with three full normal-SEM images and eight fixed motion ROIs; completed, not an active run.
- `sem/`: all 864 coarse masks/cells, fine points and measurements, all-pillar summaries and paired contrasts. No excluded cases.
- `motion_*`: saved centers, every pair and four-pair averages; no temporal SD inference.
- `pilot_training.json`, `integration_tests_v2.json`, `verification.json`: executed technical checks and their limits; none is a model promotion verdict.
- `cli_smoke/`: actual public-entry output, verified equal to the recorded D image.
- `index_registration.json`: snapshots and changed current indexes; old receipts are not rebaselined.

The canonical interpretation is [R129_RESULTS.md](../reports/R129_RESULTS.md). D is retained because it fulfills the requested architecture, not because it won every measure. No cleanup or archive deletion is scheduled.

- `organization/`: completed behavior-preserving organization checks, one public-entry real output and four intermediate states. These are technical parity checks, not new model-performance results. Architecture PNG/SVG are under `reports/figures/`.
