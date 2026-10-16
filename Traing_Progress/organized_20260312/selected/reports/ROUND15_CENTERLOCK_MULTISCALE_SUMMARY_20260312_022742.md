# ROUND15_CENTERLOCK Multiscale Summary

- best_candidate_family: centerlock_pure
- selection_policy: center-lock rank uses 0.8px center stability primary gate, 8px non-regression gate, 0.08px secondary tie-breaker; deployment checkpoint chosen by center-lock audit

| candidate | s0.08 | s0.8 | s8 | ann0.8 | seq0.8 | c0.8 | step0.8 | thick0.8 | corridor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| centerlock_pure | 13.513 | 39.824 | 64.740 | 1.0000 | 0.6969 | 0.7478 | 0.1783 | 0.0122 | 366.564 |
| centerlock_defectguard | 12.348 | 39.829 | 64.570 | 1.0000 | 0.6969 | 0.7478 | 0.1783 | 0.0122 | 365.002 |
| centerlock_balanced | 8.552 | 39.839 | 64.542 | 1.0000 | 0.6969 | 0.7478 | 0.1783 | 0.0122 | 360.481 |
| centerlock_macroguard | 8.606 | 39.775 | 64.697 | 1.0000 | 0.6969 | 0.7478 | 0.1783 | 0.0122 | 360.283 |