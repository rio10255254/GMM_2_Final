# R118 package manifest

Experiment: R118_PhysicalCoordinateRepairScratch.
Profile: self-contained small source/runtime package with immutable shared data.
Current result: repaired 12-epoch / 512-scene probe, not a full trained release.
Formal 42-epoch R118 run: not started at the 2026-09-05 verified handoff.
Promotion: none; COMBO and approved production alternates are unchanged.

## Canonical entry points

- NEXT_STEPS.md: current next-design handoff. Read this before any new training.
- reports/R118_EXECUTION_HANDOFF.md: context, scope and phase map.
- reports/R118_IMPLEMENTATION_TASKS.md: implementation/verification cards.
- reports/R118_OPERATION_RUNBOOK.md: real commands, protocol sources and recovery.
- reports/next_design_plan.json: dependencies and required evidence.
- reports/next_design_selected_ids.json: frozen metadata-only scene selection.
- reports/next_design_assets.json: protected runtime, inputs and reference hashes.
- READY.json: R118 repair evidence, NOT readiness of the next design.
- runs/RUN_INDEX.json: authoritative role of every historical local probe.

## Training and data

5,000 train / 512 development latent geometries; labels rendered at 8x before
reduction. R118 references are shared immutable hardlinks: never edit in place.
The 144-scene confirmation is not used for selection. Keep its source metadata
immutable; record future evaluation in the new work root's consumption ledger
and root handoff. No real SEM structures/pixels enter training. Real files are
evaluation-only. Sequence supervision does not change one-image deployment.
No historical weights may initialize a new independent experiment.

## Selected reference

runs/verified_physical_repair/weights/epoch_012.pth
SHA-256 b83b7748f7d128793f6e198b23242c114cae1ee6b25734a718d9d68bba515ecd.
Keep all previous failed attempts. A folder named final is not necessarily
selected; consult runs/RUN_INDEX.json.

## Next work and storage

R119_SequenceGeometryValidation is a proposed folder only. This handoff did not
create it, generate an image bank or start another trainer. Register future
storage before large allocation, reuse base references and estimate payload.
Initial new payload budget: 8 GiB; exceeding it never authorizes deletion.
This preparation adds only small text/program/check artifacts. Result roles
are in results/README.md. Do not move/thin old payload as part of this handoff.
