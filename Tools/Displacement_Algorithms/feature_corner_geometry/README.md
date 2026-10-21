# Feature Corner Geometry

This folder keeps the old MATLAB feature/corner/geometry scripts and a clean
Python entry point.

## What was selected

- `Distortion2.m`: checkerboard corner detection and projective alignment.
- `autoFlattenCheckerboard*.m`: checkerboard flattening and feature matching.
- `run_flatten.m`, `objective_func.m`, `bads_optimize.m`: support scripts used
  by the old alignment workflow.
- `Circle_Shift.m`, `Circle_Edge_Filter.m`, `Drawing_GT_only_Circle.m`,
  `Preprocess_GT_CornerBlock.m`: circle-center and GT preprocessing scripts.

The old MATLAB scripts are useful for tracing the original idea, but several
contain hard-coded paths and GUI/figure output. For repeatable displacement
tables, prefer the root `scripts/measure_feature_anchor.py` entry point.
