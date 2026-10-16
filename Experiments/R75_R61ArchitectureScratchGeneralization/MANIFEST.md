# R75 Manifest

- Status: self-contained package prepared and end-to-end verified; the invalid AMP run was stopped and excluded, and the safe full-precision 100-epoch formal run restarted at 2026-07-30 21:11 local time.
- Branch: `sandbox/r75-scratch-generalization`.
- Architecture: local frozen copy of the R61v16-compatible model, utility file, and analytic PSF bank.
- Initialization: random only; checkpoint and teacher loading are hard-disabled.
- Training population: 5,120 pure-procedural pairs from 16 shape families.
- Label rasterization: draw at 1024×1024 and area-downsample to 256×256.
- Split: 4,096 train, 512 validation, 512 internal test; grouped by geometry ID with zero overlap.
- Imaging diversity: eight degradation families plus polarity, contrast, illumination, and noise variation.
- Evaluation boundary: internal test, frozen R73/R74 synthetic contour sets, then a final frozen real-SEM blind audit.
- Live observation: the fixed thesis center-nine pillar Raw crop is reconstructed at epochs 5, 10, ..., 100 only; it has no path into loss, checkpoint selection, or training controls.
- Formal baseline status: unchanged. R75 remains a research side track until all promotion gates pass.

The experiment folder contains the model, trainer, inference program, data builder, data packages, exported weights, run logs, configuration, tests, and reports. Long run outputs and generated data remain local to this experiment folder.
