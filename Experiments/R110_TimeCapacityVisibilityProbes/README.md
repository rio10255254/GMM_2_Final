# R110 Time, Capacity, and Visibility Probes

R110 tests three mutually distinct explanations for the remaining R109 error.
The selected R109 E48 checkpoint is read-only and is never overwritten.

- `continuation`: load E48, reset only the optimizer, and train the renderer for
  eight additional epochs at 1e-5 on all 5,000 procedural scenes. This is an
  inherited-weight diagnostic and cannot become a formal independent model.
- `capacity64`: increase the local towers from 48 to 64 channels and run a
  matched 1-detector + 4-renderer epoch scratch probe on 1,000 scenes.
- `visibility`: keep 48 channels but add a bounded monotonic local visibility
  gain in addition to width and normal shift, then run the same scratch probe.

All probes use the verified R109 procedural data and fixed validation. No real
or SEM pixel is used for training. Real images are evaluated only after each
probe freezes its checkpoint.

