# Phase Correlation DFT

This folder keeps the old MATLAB DFT registration code and a clean Python
entry point.

## What was selected

- `dftregistration.m`: original subpixel DFT registration routine.
- `dftregistration_hf.m`: high-frequency filtered variant.
- `measure_displacement_consecutive_SRx2_v2.m`: old consecutive-image
  displacement script.
- `measure_displacement_consecutive_SRx2_v2_Parallel.m`: old parallel variant.
- `measure_displacement_demo*.m`: old demos.

The old MATLAB scripts contain hard-coded paths, so they are preserved as
source evidence. For new analysis, prefer the root `scripts/measure_phase_dft.py`
entry point.
