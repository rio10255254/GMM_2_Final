# R121 Boundary Anchor Factorial

Self-contained research experiment. Four arms, two independent initializations,
12 epochs each; no long training or automatic promotion.

- A: unchanged corrected R120 physical-sequence control.
- B: A plus independently varied affine intensity midpoint and contrast.
- C: A plus local normal-position checks before and after additive detail.
- D: both changes.

One paired input/target bank is used for every evaluation. Geometry, optics,
physical motion schedule, batch size, stage schedule and optimizer budget remain
identical across arms except the two declared factors. All runs start from scratch.
R118 source arrays and R120 physical sequence arrays are immutable external
references; no duplicate training payload is made. New output budget: 8 GiB.

Historical SEM masks are preserved. A separate global pitch-matched reference is
a declared sensitivity check, not a relabeling of old results or a source of
training truth. Old SEM magnification provenance is incomplete.

Branch: codex/r121-boundary-anchor, created from the existing checkout without
resetting its unrelated dirty work. No external GitHub publication is included.

## Executed result

Eight valid probes are evaluated. B/C/D fail the paired shape and texture
requirements in both initializations and both SEM references; none is adopted.
A remains the study control, not a production/thesis replacement. No long
training or conditional real-LSC follow-up was triggered.

Valid C/D use position-loss v2. The interrupted C v1 and all failure logs are
preserved and excluded from the valid matrix. Read reports/R121_RESULTS.md for
actual outcomes and reports/R121_METHODOLOGY.md for the revision history.
