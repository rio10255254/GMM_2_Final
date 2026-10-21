# R114 run registry and foreground monitor

`run_registry.py` is the single-formal-run guard.  A launcher must reserve a
run before starting a trainer, attach the trainer PID, send epoch heartbeats,
and close the run as complete, failed, or cancelled.  A second reservation is
rejected atomically while a formal run is active.

`monitor_training.ps1` opens the compact foreground view.  It tolerates a
partially written or legacy history, estimates time from recent same-stage
epochs with outlier rejection and smoothing, and shows a range rather than a
false single-point promise.  It also writes `logs/monitor_snapshot.json` for
automated inspection.

The monitor displays epoch, stage, trainer state, latest key metrics, current
GPU usage/free memory, the last epoch duration, and dynamic total remaining
time.  It never starts, stops, or modifies training.
