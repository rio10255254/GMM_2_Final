# R112 V42/R109 external-GMF mechanism decomposition

This is a frozen-model diagnostic experiment. It does not train or modify V42
or R109. The same 100 reported coordinates and 99 consecutive JunHua steps are
used for Raw, V42 E120, and R109 E48.

The experiment separates aligned-template consistency, radial edge profile,
low/high-frequency behavior, external score and scale stability, V42 module
state, and R109 midpoint/width behavior. Counterfactual output probes are used
only when an internal template locator reproduces the observed external-GMF arm
ranking. Any proposed architectural change remains provisional until it passes
SEM ACM, deterministic LSC, external GMF, line-pattern, and tile-parity checks.

## Completed finding

The internal fixed-template locator did not reproduce the external-GMF ranking,
so it was rejected for counterfactual model selection. The saved evidence shows
that V42's Raw low-frequency anchor is the dominant final-output constraint,
whereas R109 exposes much more low-frequency and spatially varying width/shift
correction. R109 already matches V42 under deterministic LSC, so the proposed
change keeps R109 geometry and replaces its final image parameterization with a
tile-safe geometric anchor plus coherent, locally zero-mean detail residual.

See `MODEL_IMPROVEMENT_DESIGN.md`, `results/mechanism_findings.json`, and
`results/final_validation.json`.
