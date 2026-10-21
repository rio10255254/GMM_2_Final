# R119 training-position diagnosis

Canonical report: ../../reports/R119_TRAINING_POSITION_DIAGNOSIS.md

Four known-answer fixture cases; frozen E24/E42 on 96 train + 96 development scenes (384 model/scene records); E42 operator fields on all 12 SEM exposures and 36 pillars. No optimizer steps, weight changes, or confirmation evaluations. 92 protected inputs unchanged.

protocol.json was written before computation. diagnose.py reproduces the calculations, verify.py checks counts, common inputs, numerical bounds, sampling sign and fresh forwards. numerical_verification.json retains the initial over-strict floating-point-check failure and its arithmetic diagnosis.

This diagnoses objective identifiability and different measured behavior, not a proven unique historical training cause. Synthetic image error and real contour error are not interchangeable.
