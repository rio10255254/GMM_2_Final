# R86 Block Group Normalization Probe

R86 keeps the exact R79 weights and optical input. It replaces image-wide GroupNorm reductions with fixed, phase-aligned 8x8 feature blocks. No training is permitted unless the zero-shot procedural and tile gates pass first.

Final status: complete and ineligible. Tile consistency passed, but reconstruction and edge errors became 1.413 and 1.964 times the R79 reference, so training was not started. The project-level resolution is recorded in `../R84_R79TileStableRootRepair/reports/R79_ROOT_REPAIR_CLOSEOUT.md`.
