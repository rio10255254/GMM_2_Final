# Branch Context

Type: research

Branch: `research/round31-b1-hparam`

Meaning:

- This branch preserves the `Round31` B1 hyperparameter tuning line as a research governance branch.
- It is semantic rather than a claim of original historical Git state.
- Use it to track the measured external regressions and the artifact caveat around `r31_eq_combo`.

Formal basis:

- `PROJECT_CURRENT_STATE.md`
- `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
- `PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

Current verdict:

- Measured `Round31` candidates regressed externally and did not replace the `Round30 / r30_b1_dironly` baseline.
- `r31_eq_combo` is recorded as `external artifact missing`, not a measured failure.
