# R116 detailed validation

## Decision

- Primary R116 research candidate: **E42**.
- Replacement of R109, R61, or V42: **not authorized**.
- E48 is not selected merely because it is the final epoch; shared SEM regressed strongly.

## What passed

- Complete scratch chain and data audit passed: 5,512 unique scenes, 0 train/validation overlap, 0 real training pixels.
- Tile parity passed: worst mean 0.000346, p99 0.002508, max 0.017851 gray.
- E42 R73 boundary improved 22.95% across 5/5 families.
- E42 shared SEM: 36/36 pillars improved; median gain 0.0326% pitch, CI95 0.0262 to 0.0356.
- E42 passed all six locked real-motion sequences with 100% direction agreement.

## What did not pass

- E42 R74 mean boundary regressed 4.28%; low-contrast and mixed-hard remain weak.
- E42 LSC step SD 8.067 nm and within-grid SD 5.456 nm trail R109/V42.
- SEM perimeter fidelity worsened in 28/36 pillars.
- External GMF package is ready but no score exists; E42 changes JunHua by only 0.0084 gray on median.

## Checkpoint roles

- E24: geometry/LSC fallback.
- E42: primary research candidate.
- E48: completed calibration artifact, not the selected model.
