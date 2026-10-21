# R119 Sequence Geometry Validation

This is the completed executable work folder for the experiment described by the
R118 handoff. Read the parent project instructions and the R118 handoff before
reusing any artifact. The package is deliberately split into measurement,
development-bank, mechanism, candidate, training and validation steps so a
completed file cannot be mistaken for a completed scientific phase.

## Current status

P00–P12 are complete and receipt-checked. Run `python scripts/status.py` for the
current phase and `python scripts/setup.py --check` for a read-only setup check.
The setup checker never starts training. The final candidate is
`runs/formal_B_s1195001/weights/epoch_042.pth`; see reports/CLOSEOUT.md.

## Planned arms

- A: unchanged R118 model/objective and original paired observation schedule.
- B: A plus coherent same-object sequence observation scheduling.
- C: B plus the one geometric mechanism supported by P04, if any.
- D: B plus targeted asymmetric optical observations only.

The arms shared scene IDs, data/sampler seeds and step budgets. No arm was chosen
from a favorable frame or checkpoint. The one formal B run used fresh random
initialization and its confirmation is now consumed; do not retune this folder.

## Important distinction

`data/package` is a shared read-only reference. New generated observations live
under this folder. `validation/inputs/Raw` contains copied camera-original bytes
for checks, not training data. Development ACM/SEM/LSC outputs cannot replace a
sealed confirmation result. A lower loss or a visually sharper panel alone is
not a promotion decision.
