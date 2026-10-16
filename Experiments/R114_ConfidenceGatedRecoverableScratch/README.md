# R114 Confidence-Gated Recoverable MOSR

R114 is an independent, scratch-only, single-image MOSR experiment.  It is
designed to fix the controller collapse, training-population imbalance,
clear/degraded gradient conflict, scalar-width supervision, unrecoverable-detail
hallucination, real microscopy domain gap, and large-image tile-consistency
risks established by the R113 causal audit.

## Scientific contract

- Every probe and the formal arm starts from a new random initialization.
- Existing target/mask/SDF arrays are read-only; real and SEM images are never
  used as training labels.
- The model uses local operations only and must pass full-versus-tiled parity.
- ACM, deterministic localization, real-sequence stability, identity safety,
  and worst-case failures are evaluated before optional external-GMF
  compatibility.
- No probe checkpoint is a delivery model.

## Campaign order

1. Prepare and audit the composition-aware data manifest.
2. Run the controller viability probe.
3. Only if the controller is spatially alive, run the geometry probe.
4. Run matched geometry-only and recoverability-gated detail probes.
5. Lock the supported design and start one formal scratch run.
6. Run the complete physical and tile validation suite before export.

The PowerShell files under `scripts` are intended to be simple manual entry
points.  The editable defaults live in the JSON files under `config`.
