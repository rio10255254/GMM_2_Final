# R120 Physical Sequence Repair

Profile: self-contained. Status: repair implementation and bounded validation.
Reference model/operators/objective: R118, copied source; no inherited weights.
Large data: immutable absolute reference to the existing R118 5000/512 package.
No junctions or writable copies of shared labels. New observations are stored
only under this folder. Real SEM and Raw images are evaluation-only.

This round addresses R119's verified deviations: actual 8x image formation,
foreground-positive geometry, shared evaluation bytes, consumed sequence
manifests, individually isolated controls and enforced locator validity.
No existing confirmation data are used for selection. It has been consumed.
The initial task completes when these repairs pass behavioral checks and a
bounded scratch comparison executes on the resulting data. A formal run needs
scientific evidence from those probes; it is not launched by a readiness file.

Single-image/tile-safe inference remains the contract. Preserve historical runs.
New payload budget: 8 GiB; register before generation. The existing dirty Git
worktree is preserved; no branch reset or external GitHub write is part of this
local workflow. Read reports/R120_RESULTS.md for actual verification status.
