# R85 Shared-Canvas Optical Repair

R85 keeps the R84 tile-stable local network, restores the original R79 optical preconditioner once per canonical canvas, and uses R79 only as an auxiliary behavior-preservation constraint on procedural inputs. Analytic supersampled labels remain the primary targets. No SEM or real microscope pixel enters training.

Run order:

1. `scripts/r85_dataset.py --profile locked_holdout`
2. `training/train_r85.py`
3. `scripts/screen_checkpoints.py`
4. Final confirmation only after a checkpoint is frozen.

Final status: complete and not selected. Both screened checkpoints passed tile consistency but exceeded the locked R79 edge limit, so the new external holdout stayed sealed and R79 remained the fallback. The project-level resolution is recorded in `../R84_R79TileStableRootRepair/reports/R79_ROOT_REPAIR_CLOSEOUT.md`.
