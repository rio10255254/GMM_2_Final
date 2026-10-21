# R119 closeout

The R118 plan was executed through P12. R119 B E42 is a completed scratch
experiment, not an automatic replacement for COMBO, V42, R61 or R109.

## Confirmation result

The reserved 144-scene synthetic confirmation was consumed exactly once after
the design and checkpoint were frozen. It contained 12 scenes in each of the
12 geometry families; no scene was used in training or selection. The source
seal remains byte-identical and its consumption is recorded in
`results/confirmation/consumption.json`.

Across the confirmation set, median image error changed from 1.572 gray levels
for Raw to 0.415 for R119 B E42. Median gradient error changed from 0.00750 to
0.00179. Every family improved these image-level measures, although dense-array
scenes showed a smaller gain than the other families.

The post-hoc fixed-reference position diagnostic is not the locked real LSC
protocol. Its median error was similar to Raw (about 0.91 vs 0.92 px), but two
model observations were clear outliers (rectangle 0086 about 18.1 px and dense
array 0021 about 3.6 px). They are retained as a warning about position
generalization; no second confirmation inference or tuning was performed.

## Final interpretation

R119 B E42 is strong on synthetic detail and the locked ACM development suites,
and it improves Raw's real LSC step variation. It does not dominate every
historical model: R109/V42 retain better fine-grid LSC stability, and the formal
SEM development comparison was slightly negative. The training objective and
single-image/tile-safe interface remain unchanged; the useful intervention was
coherent observation scheduling.

The formal model is therefore a documented research candidate. Any future
architecture or data change requires a new round and a new final confirmation
set. This consumed set must never be reused for tuning or a new promotion claim.
