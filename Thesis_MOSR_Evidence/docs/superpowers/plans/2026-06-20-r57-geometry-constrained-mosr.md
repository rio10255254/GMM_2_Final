# R57 Geometry-Constrained MOSR Plan

## Goal

Build the next LabSystem_MOSR experiment as a fine-tuned successor to R55 that
keeps the useful displacement-stability path while adding explicit geometry and
CD safeguards for the HS-100MG / Basler ace acA2040-120um sample.

## Completion Criteria

- R57 has a documented experiment package under `LabSystem_MOSR/Experiments`.
- R57 has a reproducible data-preparation path that can build a geometry/CD
  anchor package without editing the base R55 package.
- R57 training can be launched as an R55 best-tradeoff fine-tune, with PSF
  forward loss disabled by default.
- A CD gate can reject candidates that make the current 100MG sample worse than
  the original image in SEM-referenced radius error.
- Unit/smoke tests pass for the new dataset builder, launcher, and CD gate.
- A short smoke training path is available before any formal long run.

## Design

R57 is not a thesis reset. It is a geometry-constrained continuation of the R55
line. The model architecture stays the same at first. The first change is in the
training data, loss weights, fine-tune checkpoint, and model-selection gate.

The training package combines:

- the existing R55 source-style repaired R53 training package;
- HS-100MG / Basler synthetic anchor images generated at 69 nm/px from the SEM
  radius references;
- geometry sidecars for boundary, centerline, and distance-edge supervision.

The training launcher:

- defaults to fine-tuning the R55 best-tradeoff checkpoint;
- resets optimizer and epoch counters for a clean R57 run;
- disables PSF-forward loss by default because the current sample does not have
  a recalibrated PSF;
- strengthens boundary/distance supervision while reducing over-sharpening
  pressure;
- keeps sequence displacement losses enabled so CD tuning does not erase the
  thesis displacement objective.

The CD gate:

- uses the Basler-corrected 100MG measurement summary as the reference;
- compares a candidate reconstruction against the original image per feature
  type;
- fails if the candidate worsens either pillar or via SEM-referenced radius
  error beyond tolerance.

## Implementation Steps

1. Add R57 experiment docs.
2. Add tests for the R57 dataset builder, launcher, and CD gate.
3. Implement the dataset builder.
4. Implement the launcher.
5. Implement the CD gate.
6. Run tests, dry-run launcher, run CD gate on current R55 reconstructions, and
   run a short smoke training pass if the local environment supports it.

