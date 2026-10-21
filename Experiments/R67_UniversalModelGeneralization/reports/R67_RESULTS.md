# R67 Results

## Outcome

- Current-data winner: **R61v16**.
- Universal promotion: **not yet allowed**.
- Reconstruction coverage: 24 model-sequence runs, 1206 frame outputs checked.
- Reason: the available four sequences overlap the development domain and do not provide independent motion truth.

## Worst-case-first ranking

| Rank | Model | Circular failures | Unavailable steps | Worst-case regret | P90 regret | Median regret | Universal pass |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | R61v16 | 0 | 0 | 8.209 | 2.385 | 1.280 | No |
| 2 | R38v2 | 0 | 0 | 10.482 | 1.970 | 1.278 | No |
| 3 | V42E120 | 0 | 0 | 32.747 | 1.960 | 1.210 | No |
| 4 | R39R40 | 4 | 5 | 9.404 | 1.890 | 1.070 | No |
| 5 | R33 | 8 | 10 | 28.394 | 2.100 | 1.160 | No |
| 6 | COMBO | 7 | 32 | 4.063 | 2.080 | 1.092 | No |

A regret of 1.0 is best in that measurement cell. Excess error is scaled by the typical candidate result in the same cell, including cells whose best error is zero. The primary score is the single worst cell, so a model cannot hide a bad scene behind a strong average.

## Required final gate

Populate `config/phase_b_holdout.template.json` with sealed new sample lots, fields of view, focus/signal conditions, and independent motion/CD references. Run the same frozen candidates without tuning. Only then can one model receive the universal label.

## Reproducibility

The main script validates every checkpoint and input count, resumes complete reconstruction folders, runs the three locked measurement protocols, calculates the ranking, and rewrites this report.
