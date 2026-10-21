# R89 Measurement-Native Scratch

R89 is one independent, from-scratch reconstruction experiment. It keeps the
R88 encoder-decoder and local optical backbone, removes the output confidence
gate, and trains one direct bounded reconstruction for contour, texture,
sub-pixel displacement, and tiled-image consistency together.

## Fixed rules

- No inherited checkpoint, resume, teacher, pseudo-label, SEM structure, or
  HS100MG structure is accepted by the trainer.
- Every label is drawn at 8x resolution and antialiased down to the stored
  resolution.
- Over-strong synthetic corruption is reduced with one image-wide scale; the
  generator rejects target-shaped pixelwise clipping above 0.0200%.
- Real 5x, 20x, and 50x images contribute aggregate noise and illumination
  statistics only. No real image pixels, contours, positions, or spacing enter
  training pairs.
- The formal run is limited to one 100-epoch random initialization.
- Real live-validation images are reconstructed for visual monitoring only;
  they cannot select a checkpoint.

## Folder guide

- `config`: locked design, acceptance gates, authorization, optical summary,
  and implementation hashes.
- `data`: generated smoke/formal/holdout packages plus four fixed real preview
  images.
- `model`: the reconstruction architecture.
- `training`: the editable training program and loss definitions.
- `inference`: the canonical full-image tiled reconstruction program.
- `scripts`: data generation, checks, launchers, and the foreground monitor.
- `runs`: immutable run records and plain-text logs.
- `weights`: checkpoints grouped by smoke/formal run and seed.
- `results`: dataset previews, real before/after previews, and benchmark reports.
- `reports`: human-readable design and preflight evidence.

## Manual commands

Run from this folder with `C:\Users\Rio\anaconda3\python.exe`.

```powershell
# Check the locked design
python scripts\validate_design.py

# Run unit and integration tests
python -m pytest -q

# Start the single formal run and open the foreground monitor
powershell -ExecutionPolicy Bypass -File scripts\start_formal_training.ps1

# Open only the monitor
powershell -ExecutionPolicy Bypass -File scripts\monitor_training.ps1
```

The selected checkpoint is written only when it passes all internal safety
gates. A diagnostic best checkpoint is also retained, but it must not be
treated as a deployable model unless the final validation report passes.
