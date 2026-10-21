# R68 Manifest

## Frozen model

- Candidate: R61v16.
- Checkpoint: the formal `best_tradeoff` checkpoint from the 2026-06-23 eight-epoch run.
- Inference mode: the previously locked real-sample PSF-off mode.

## Data

- 5x, 0.5 um: 50 frames.
- 5x, 1.0 um: 50 frames.
- 20x, 0.5 um: 50 frames.
- 20x, 1.0 um: 50 frames.
- 50x, 0.5 um: 51 frames.
- 50x, 1.0 um: 50 frames.

## Evidence boundary

The acquisition dates are later than the frozen R61v16 checkpoint. The same images were later used by V42, but that does not affect their external status for R61v16. Sample identity between the 2026-07-02 and 2026-07-04 acquisitions is not asserted without an acquisition log.

## Outputs

- `results/input_audit.json`: source and reconstruction validation.
- `results/tables/tile_motion_measurements.csv`: all local measurements.
- `results/tables/sequence_summary.csv`: one decision row per sequence.
- `results/gate_decision.json`: machine-readable pass/fail.
- `reports/R68_RESULTS.md`: concise result.

