# R119 Sequence Geometry Validation

Status: complete execution from the R118 handoff. New work was isolated here.
R119 B E42 is a completed research candidate; it is not a promoted model.

## Scope

Single-image inference remains the deployment contract, including native large-
image tiling. Sequence observations are used only to diagnose and train against
repeatable physics. Training remains procedural: roughly 5,000 independent
synthetic geometries, labels rendered at 8x before reduction, no real SEM/Raw
pixels or copied sample structures, and every model seed starts from scratch.
The thesis readouts are ACM shape, stable displacement and faithful detail.
External GMF remains an industry-side diagnostic, not a thesis gate.

## Sources and identity

The unchanged R118 numerical source is copied into model/, training/ and
inference/ with hashes recorded in config/base_snapshot.json. The large R118
package is reused through the immutable directory reference
data/package -> R118_PhysicalCoordinateRepairScratch/data/package; do not write
through it. Real Raw previews are copied byte-identically under
validation/inputs/Raw and are evaluation-only. R109 is a frozen comparison, not
a teacher. The 144-scene confirmation remains outside this work root and must
not be opened for selection before P12.

## Execution state

P00–P12 are complete and receipt-checked. The final candidate is
`runs/formal_B_s1195001/weights/epoch_042.pth`; see reports/CLOSEOUT.md.
See reports/R118_EXECUTION_HANDOFF.md, R118_MEASUREMENT_CONTRACT.md,
R118_IMPLEMENTATION_TASKS.md and R118_OPERATION_RUNBOOK.md for the complete
contract. The current R118 E12 checkpoint is a reference only; this R119 work
does not warm-start from it.

Storage registry registration occurs before generating substantial sidecars.
The initial new-payload budget is 8 GiB. Estimate bytes from a pilot first;
reuse links and compressed sidecars before considering any cleanup. Historical
files are not deleted by this experiment.
