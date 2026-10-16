# R101 High-Frequency Causal Ablation

This folder contains the short A/B/C falsification that must run before a full
R101 scratch training is authorized.

- Arm A: R100 causal operator with physically paired continuous-scene data.
- Arm B: Arm A plus phase-coherent multi-scale weak-edge support.
- Arm C: Arm B plus a bounded subpixel boundary renderer and forward optical
  data consistency.

All arms use the same generated scenes, batch schedule, common initialization,
optimizer settings and validation images.  No real SEM or HS100MG structure is
used for training.  Real images are evaluation-only.

Use `scripts/run_all.ps1` to regenerate missing data, train all three arms and
run the final comparison.  Existing completed outputs are never overwritten
unless `-Force` is passed explicitly.

