# L0 New-Data Formal Summary

- Generated: 2026-07-07T23:18:03
- Formal L0 rule: one capture set repeated through the fitter.
- Formal L0 capture: Circle_Round1.
- L1 source rule: Circle_Round1/2/3 are separate capture repeats.
- Round2/Round3 are retained as L1 source diagnostics, not aggregated into the formal L0 readout.
- Data rule: 11x11 grid, old nine-point pattern, frame 1 from each two-frame position pair.
- Fit target: circle boundary only; center square blocks are masked.
- Legacy L0 outputs were archived under `archive_L0_legacy_20260616`.

## Formal L0 Result

| Round | Trials | Clean median | Clean mean | FOV max/min | Mean fit value | Report |
|---|---:|---:|---:|---:|---:|---|
| Circle_Round1 | 15 | 0.027055 | 0.065377 | 1.211 | 14952.42 | L0_newdata_noise_floor_report.md |

## L1 Source Fit Inventory

These completed repeated-fit runs are useful for L1, but they are not part of the formal L0 aggregate.

| Round | Role | Trials | Repeat-fit median | Repeat-fit mean | FOV max/min | Mean fit value |
|---|---|---:|---:|---:|---:|---:|
| Circle_Round2 | L1_source_only | 15 | 0.022559 | 0.051162 | 1.377 | 14993.76 |
| Circle_Round3 | L1_source_only | 15 | 0.027294 | 0.058550 | 1.194 | 14793.45 |

## Source Inventory Diagnostic

- Median of all completed round medians: 0.027055
- Mean of all completed round medians: 0.025636
- Std of all completed round medians: 0.002667
- Mean of all completed round means: 0.058363
- This section is only a source-inventory sanity check, not the formal L0 definition.

## Interpretation Guardrails

- Formal L0 is Circle_Round1 repeated through the fitter 15 times.
- Circle_Round2/3 are separate captures and belong to the L1 comparison layer.
- The two same-position frames are acquisition duplicates; frame 2 is handled by the paired-frame supplemental check.