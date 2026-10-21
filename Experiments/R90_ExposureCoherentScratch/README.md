# R90 Exposure-Coherent Scratch

R90 is one independent reconstruction experiment trained from random weights.
It preserves the R89 tile-safe architecture and detail capability, while
directly addressing exposure-dependent contour drift and the dark outline seen
in 5x images.

## What changed

- The low-frequency correction branch is now truly low-pass, so it cannot draw
  a narrow dark contour.
- The same procedural structure is observed under four coherent exposure
  conditions and trained to return to one contour position.
- Training alternates between overlapping-tile pairs, cross-observation pairs,
  and signed-motion pairs.
- Loss strengths rise smoothly rather than switching abruptly.
- Checkpoints are ranked by a continuous balanced score. Diagnostic references
  are reported, not used as binary checkpoint gates.

## Data isolation

- 1,280 procedural scenes and 5,120 formal observations.
- Every label is drawn at 8x resolution and antialiased once when reduced.
- No SEM or HS100MG pixel, contour, structure, checkpoint, teacher output, or
  pseudo-label is used for training.
- Real 5x, 20x and 50x data contribute anonymous aggregate optical statistics
  only.
- A separate 384-scene holdout is sealed and unavailable to training or
  checkpoint selection.

## Folder guide

- `config`: editable experiment, training and diagnostic settings.
- `model`: the R90 architecture.
- `training`: the directly runnable training program.
- `inference`: full-image and tiled reconstruction.
- `scripts`: dataset generation, verification, monitoring and launch helpers.
- `data`: formal data, sealed holdout and four fixed live-validation inputs.
- `weights`: scratch checkpoints created by this experiment only.
- `results`: live reconstruction previews and verification reports.
- `runs`: progress records and training logs.

## Start and monitor

The formal run is launched with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_formal_training.ps1
```

The launcher opens a foreground monitor and runs training in a separate hidden
process. It reconstructs the four fixed real images at epoch 1 and every five
epochs thereafter. The training program can also be opened directly in an IDE;
all tunable values are in `config/experiment_design.json`.

There is intentionally no checkpoint or resume input. Formal training can be
registered only once, which protects the independence of this run.

## Post-run result

Training was stopped after the fully completed epoch 55.  A locked comparison
of epochs 20 through 55 found epoch 45 to be the last useful checkpoint before
the clear 5x dark-outline regression that begins at epoch 50.  Epoch 45 keeps
stable motion and exact tiled reconstruction, but a real SEM exposure condition
still moves the contour outward.  It is therefore retained as a research and
ONNX-feasibility candidate, not promoted to enterprise delivery or to the
formal project baseline.  The measured diagnosis and the next independent
scratch-round design are indexed in `MANIFEST.md`.
